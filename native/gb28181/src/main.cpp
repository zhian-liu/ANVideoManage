#include <resip/stack/Helper.hxx>
#include <resip/stack/BasicNonceHelper.hxx>
#include <resip/stack/PlainContents.hxx>
#include <resip/stack/SipStack.hxx>
#include <resip/stack/SipMessage.hxx>
#include <resip/stack/ParameterTypes.hxx>
#include <rutil/Logger.hxx>
#include <httplib.h>
#include <nlohmann/json.hpp>

#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdlib>
#include <deque>
#include <fstream>
#include <functional>
#include <future>
#include <iostream>
#include <map>
#include <memory>
#include <mutex>
#include <random>
#include <regex>
#include <string>
#include <thread>

using Json = nlohmann::json;
using namespace resip;
using Clock = std::chrono::steady_clock;
static std::atomic<bool> interrupted{false};
static constexpr size_t MaxBody = 256 * 1024;

static std::string str(const Data& value) { return {value.data(), value.size()}; }
static Data data(const std::string& value) { return Data(value.data(), value.size()); }
static Data rawBody(const SipMessage& message) {
    const auto& body = message.getRawBody();
    return body.getLength() ? Data(body.getBuffer(), body.getLength()) : Data::Empty;
}
static long long epoch() {
    return std::chrono::duration_cast<std::chrono::seconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
}
static std::string randomId() {
    std::random_device random;
    std::string result;
    for (int i = 0; i < 32; ++i) result += "0123456789abcdef"[random() & 15];
    return result;
}
static bool isId(const std::string& value) {
    return value.size() == 20 && value.find_first_not_of("0123456789") == std::string::npos;
}
static bool sameSource(const Tuple& a, const Tuple& b) {
    return a.getType() == b.getType() && a.getPort() == b.getPort()
        && a.presentationFormat() == b.presentationFormat()
        && (a.getType() != TCP || a.getFlowKey() == b.getFlowKey());
}
static bool secureEqual(const std::string& a, const std::string& b) {
    size_t diff = a.size() ^ b.size();
    for (size_t i = 0; i < a.size() && i < b.size(); ++i) diff |= a[i] ^ b[i];
    return diff == 0;
}
class SourceNonceHelper : public BasicNonceHelper {
    const std::string secret_ = randomId();
public:
    Data makeNonce(const SipMessage& request, const Data& timestamp) override {
        const auto& source = request.getSource();
        // Authentication runs on the SIP loop. Bind a challenge to its source,
        // including the TCP flow, so legacy Digest can re-register safely too.
        setPrivateKey(data(secret_ + ":" + str(source.presentationFormat()) + ":"
            + std::to_string(source.getPort()) + ":" + std::to_string(static_cast<int>(source.getType()))
            + ":" + std::to_string(source.getType() == TCP ? source.getFlowKey() : 0)));
        return BasicNonceHelper::makeNonce(request, timestamp);
    }
};
struct ApiError : std::runtime_error {
    int status;
    ApiError(int code, const char* message) : std::runtime_error(message), status(code) {}
};

struct Registration {
    Tuple source;
    NameAddr contact;
    long long expires = 0;
};
struct Session {
    std::string id;
    std::string device;
    Tuple source;
    std::unique_ptr<SipMessage> invite;
    std::unique_ptr<SipMessage> answer;
    std::string state = "inviting";
    bool cancelled = false;
    bool provisional = false;
    bool cancelSent = false;
    bool byeSent = false;
    Clock::time_point deadline;
    Clock::time_point retainUntil = Clock::time_point::max();
};

// All SIP/application state lives on the SIP loop. HTTP workers only submit jobs.
class Service {
public:
    Service(Json config, std::string token)
        : config_(std::move(config)), token_(std::move(token)), instance_(randomId()) {
        const auto sipId = config_.at("sip_id").get<std::string>();
        if (!isId(sipId) || token_.size() < 32) throw std::runtime_error("Invalid service identity/token");
        const int port = config_.at("sip_port").get<int>();
        if (port < 1 || port > 65535) throw std::runtime_error("Invalid SIP port");
        const auto bind = data(config_.at("listen_ip").get<std::string>());
        stack_.addTransport(UDP, port, V4, StunDisabled, bind);
        stack_.addTransport(TCP, port, V4, StunDisabled, bind);
        from_ = NameAddr(data("sip:" + sipId + "@" + config_.at("realm").get<std::string>()));
        contact_ = NameAddr(data("sip:" + sipId + "@" + config_.at("advertise_ip").get<std::string>()
            + ":" + std::to_string(port)));
        setupHttp();
    }

    void run() {
        const int port = config_.at("http_port").get<int>();
        if (!http_.bind_to_port("127.0.0.1", port)) throw std::runtime_error("Internal HTTP port is occupied");
        std::thread httpThread([this] { http_.listen_after_bind(); });
#ifdef _WIN32
        HANDLE parent = nullptr;
        if (config_.value("parent_pid", 0) > 0)
            parent = OpenProcess(SYNCHRONIZE, FALSE, config_.at("parent_pid").get<DWORD>());
#endif
        try {
            while (!interrupted && Clock::now() < quitAt_) {
                drainJobs();
                stack_.process(20);
                while (auto raw = stack_.receive()) {
                    std::unique_ptr<SipMessage> message(raw);
                    try {
                        if (message->isRequest()) onRequest(*message);
                        else if (message->isResponse()) onResponse(*message);
                    } catch (const std::exception&) {
                        // No raw SIP/Authorization/XML in logs, including parser exceptions.
                        std::cerr << "Rejected malformed SIP message\n";
                        if (message->isRequest()) {
                            try { respond(*message, 400); } catch (...) {}
                        }
                    } catch (...) {
                        std::cerr << "Rejected invalid SIP message\n";
                    }
                }
                tick();
#ifdef _WIN32
                if (parent && WaitForSingleObject(parent, 0) == WAIT_OBJECT_0) break;
#endif
            }
            for (auto& item : sessions_) terminate(item.second);
            const auto end = Clock::now() + std::chrono::milliseconds(500);
            while (Clock::now() < end) stack_.process(20);
        } catch (...) {
            http_.stop();
            httpThread.join();
#ifdef _WIN32
            if (parent) CloseHandle(parent);
#endif
            throw;
        }
        http_.stop();
        httpThread.join();
#ifdef _WIN32
        if (parent) CloseHandle(parent);
#endif
    }

private:
    Json config_;
    std::string token_;
    std::string instance_;
    SipStack stack_;
    NameAddr from_;
    NameAddr contact_;
    httplib::Server http_;
    std::map<std::string, std::string> credentials_;
    std::map<std::string, Registration> registrations_;
    std::map<std::string, Session> sessions_;
    std::map<std::string, std::pair<unsigned long, long long>> replay_;
    std::deque<Json> events_;
    size_t eventBytes_ = 0;
    unsigned long long sequence_ = 0;
    std::mutex jobsMutex_;
    std::deque<std::function<void()>> jobs_;
    Clock::time_point quitAt_ = Clock::time_point::max();

    void emit(Json event) {
        event["seq"] = ++sequence_;
        event["time"] = epoch();
        eventBytes_ += event.dump().size();
        events_.push_back(std::move(event));
        while (events_.size() > 1024 || eventBytes_ > 8 * 1024 * 1024) {
            eventBytes_ -= events_.front().dump().size();
            events_.pop_front();
        }
    }
    Json submit(std::function<Json()> operation) {
        auto task = std::make_shared<std::packaged_task<Json()>>(std::move(operation));
        auto future = task->get_future();
        {
            std::lock_guard<std::mutex> guard(jobsMutex_);
            if (jobs_.size() >= 128) throw ApiError(503, "SIP command queue is full");
            jobs_.emplace_back([task] { (*task)(); });
        }
        if (future.wait_for(std::chrono::seconds(5)) != std::future_status::ready)
            throw ApiError(503, "SIP command timed out");
        return future.get();
    }
    void drainJobs() {
        std::deque<std::function<void()>> pending;
        { std::lock_guard<std::mutex> guard(jobsMutex_); pending.swap(jobs_); }
        for (auto& task : pending) task();
    }
    template<class F> void endpoint(const httplib::Request& req, httplib::Response& response, F fn) {
        response.set_header("Cache-Control", "no-store");
        if (!secureEqual(req.get_header_value("Authorization"), "Bearer " + token_)) {
            response.status = 401;
            response.set_content("{\"error\":\"Unauthorized\"}", "application/json");
            return;
        }
        try {
            const auto result = submit(fn);
            response.set_content(result.dump(), "application/json");
        } catch (const ApiError& error) {
            response.status = error.status;
            response.set_content(Json{{"error", error.what()}}.dump(), "application/json");
        } catch (const std::exception&) {
            response.status = 400;
            response.set_content("{\"error\":\"Invalid command\"}", "application/json");
        }
    }
    void setupHttp() {
        http_.set_payload_max_length(512 * 1024);
        http_.set_read_timeout(5, 0);
        http_.set_write_timeout(5, 0);
        http_.Get("/health", [this](const auto& req, auto& res) {
            endpoint(req, res, [this] { return Json{{"status", "ok"}, {"instance", instance_},
                {"version", "0.1.0"}, {"sip_id", config_.at("sip_id")}}; });
        });
        http_.Put("/v1/devices", [this](const auto& req, auto& res) {
            endpoint(req, res, [this, body = req.body] {
                auto incoming = Json::parse(body);
                if (!incoming.is_array() || incoming.size() > 10000) throw ApiError(400, "Invalid devices");
                std::map<std::string, std::string> replacement;
                for (const auto& item : incoming) {
                    auto id = item.at("id").template get<std::string>();
                    auto password = item.at("password").template get<std::string>();
                    if (!isId(id) || password.empty() || password.size() > 512)
                        throw ApiError(400, "Invalid credential");
                    if (item.value("enabled", true)) replacement[id] = password;
                }
                for (auto it = registrations_.begin(); it != registrations_.end();) {
                    if (!replacement.count(it->first) || credentials_[it->first] != replacement[it->first]) {
                        disconnect(it->first);
                        it = registrations_.erase(it);
                    } else ++it;
                }
                credentials_ = std::move(replacement);
                return Json{{"ok", true}};
            });
        });
        http_.Get("/v1/events", [this](const auto& req, auto& res) {
            endpoint(req, res, [this, cursor = req.get_param_value("after")] {
                const auto after = cursor.empty() ? 0ULL : std::stoull(cursor);
                const auto oldest = events_.empty() ? sequence_ + 1 : events_.front()["seq"].get<unsigned long long>();
                Json batch = Json::array();
                for (const auto& event : events_) {
                    if (event["seq"].get<unsigned long long>() > after) batch.push_back(event);
                    if (batch.size() == 64) break;
                }
                return Json{{"instance", instance_}, {"events", batch}, {"latest", sequence_},
                    {"gap", after + 1 < oldest || after > sequence_}};
            });
        });
        http_.Post("/v1/message", [this](const auto& req, auto& res) {
            endpoint(req, res, [this, body = req.body] {
                auto command = Json::parse(body);
                const auto id = command.at("device_id").get<std::string>();
                const auto& registration = registered(id);
                auto bytes = data(command.at("body_base64").get<std::string>()).base64decode();
                if (bytes.size() > MaxBody) throw ApiError(400, "Message too large");
                auto message = request(id, registration, MESSAGE);
                message->setContents(std::make_unique<PlainContents>(bytes, Mime("Application", "MANSCDP+xml")));
                auto callId = str(message->header(h_CallId).value());
                stack_.sendTo(*message, registration.source);
                return Json{{"call_id", callId}};
            });
        });
        http_.Post("/v1/invite", [this](const auto& req, auto& res) {
            endpoint(req, res, [this, body = req.body] { return invite(Json::parse(body)); });
        });
        http_.Delete(R"(/v1/sessions/([a-f0-9]{32}))", [this](const auto& req, auto& res) {
            endpoint(req, res, [this, id = req.matches[1].str()] {
                auto it = sessions_.find(id);
                if (it != sessions_.end()) terminate(it->second);
                return Json{{"ok", true}};
            });
        });
        http_.Post("/v1/shutdown", [this](const auto& req, auto& res) {
            endpoint(req, res, [this] {
                quitAt_ = Clock::now() + std::chrono::milliseconds(200);
                return Json{{"ok", true}};
            });
        });
    }

    void respond(const SipMessage& request, int status) {
        stack_.send(std::unique_ptr<SipMessage>(Helper::makeResponse(request, status)));
    }
    const Registration& registered(const std::string& id) {
        auto it = registrations_.find(id);
        if (it == registrations_.end() || it->second.expires <= epoch())
            throw ApiError(409, "Device is not registered");
        return it->second;
    }
    std::unique_ptr<SipMessage> request(const std::string& targetId, const Registration& registration, MethodTypes method) {
        NameAddr target = registration.contact;
        target.uri().user() = data(targetId);
        auto result = std::unique_ptr<SipMessage>(Helper::makeRequest(target, from_, contact_, method));
        result->header(h_To) = NameAddr(data("sip:" + targetId + "@" + config_.at("realm").get<std::string>()));
        return result;
    }
    void disconnect(const std::string& id) {
        emit({{"type", "registration"}, {"device_id", id}, {"expires", 0}});
        for (auto& item : sessions_) if (item.second.device == id) terminate(item.second);
    }
    void onRegister(const SipMessage& message) {
        const auto id = str(message.header(h_From).uri().user());
        if (!isId(id) || !credentials_.count(id) || str(message.header(h_To).uri().user()) != id) {
            respond(message, 403);
            return;
        }
        const auto realm = data(config_.at("realm").get<std::string>());
        if (!message.exists(h_Authorizations) || message.header(h_Authorizations).empty()) {
            stack_.send(std::unique_ptr<SipMessage>(Helper::makeWWWChallenge(message, realm)));
            return;
        }
        const auto& auth = message.header(h_Authorizations).front();
        if (message.header(h_Authorizations).size() != 1 || message.exists(h_ProxyAuthorizations)
            || !auth.exists(p_username) || str(auth.param(p_username)) != id
            || !auth.exists(p_uri) || Uri(auth.param(p_uri)) != message.header(h_RequestLine).uri()) {
            respond(message, 403);
            return;
        }
        auto result = Helper::authenticateRequest(message, realm, data(credentials_.at(id)), 300);
        if (result != Helper::Authenticated) {
            stack_.send(std::unique_ptr<SipMessage>(Helper::makeWWWChallenge(message, realm, true, result == Helper::Expired)));
            return;
        }
        auto replayKey = id + ":" + str(auth.param(p_nonce));
        unsigned long counter = message.header(h_CSeq).sequence();
        if (auth.exists(p_qop)) {
            // CSeq/Call-ID are not covered by the Digest hash. qop replay
            // protection must use its authenticated nonce count and cnonce.
            const auto count = str(auth.param(p_nc));
            if (count.size() != 8 || count.find_first_not_of("0123456789abcdefABCDEF") != std::string::npos
                || auth.param(p_cnonce).empty()) {
                respond(message, 403);
                return;
            }
            counter = std::stoul(count, nullptr, 16);
            replayKey += ":qop:" + str(auth.param(p_cnonce));
        } else {
            // Legacy Digest uses CSeq ordering within its source-bound nonce.
            replayKey += ":legacy:" + str(message.header(h_CallId).value());
        }
        if (!counter || (replay_.count(replayKey) && counter <= replay_[replayKey].first)) {
            respond(message, 403);
            return;
        }
        unsigned int expires = message.exists(h_Expires) ? message.header(h_Expires).value() : 3600;
        if (message.exists(h_Contacts) && !message.header(h_Contacts).empty()
            && message.header(h_Contacts).front().exists(p_expires))
            expires = message.header(h_Contacts).front().param(p_expires);
        expires = std::min(expires, 86400U);
        if (expires && (!message.exists(h_Contacts) || message.header(h_Contacts).empty()
            || message.header(h_Contacts).front().isAllContacts())) {
            respond(message, 400);
            return;
        }
        replay_[replayKey] = {counter, epoch() + 300};
        if (replay_.size() > 20000) replay_.erase(replay_.begin());
        auto response = std::unique_ptr<SipMessage>(Helper::makeResponse(message, 200));
        response->header(h_Expires).value() = expires;
        if (message.exists(h_Contacts)) response->header(h_Contacts) = message.header(h_Contacts);
        if (!response->header(h_Contacts).empty()) response->header(h_Contacts).front().param(p_expires) = expires;
        stack_.send(*response);
        if (!expires) {
            registrations_.erase(id);
            disconnect(id);
            return;
        }
        auto source = message.getSource();
        source.onlyUseExistingConnection = source.getType() == TCP;
        if (registrations_.count(id) && !sameSource(registrations_.at(id).source, source)) disconnect(id);
        registrations_[id] = Registration{source, message.header(h_Contacts).front(), epoch() + expires};
        emit({{"type", "registration"}, {"device_id", id}, {"expires", expires},
            {"remote_ip", str(source.presentationFormat())}, {"remote_port", source.getPort()},
            {"transport", source.getType() == TCP ? "TCP" : "UDP"}});
    }
    void onRequest(const SipMessage& message) {
        const auto method = message.header(h_RequestLine).method();
        if (method == REGISTER) { onRegister(message); return; }
        if (method == ACK) return;
        if (method == BYE) {
            for (auto& item : sessions_) {
                auto& session = item.second;
                if (session.invite->header(h_CallId).value() == message.header(h_CallId).value() && session.answer
                    && sameSource(session.source, message.getSource())
                    && message.header(h_To).param(p_tag) == session.invite->header(h_From).param(p_tag)
                    && message.header(h_From).param(p_tag) == session.answer->header(h_To).param(p_tag)) {
                    respond(message, 200);
                    finish(session, "ended", "Device ended session");
                    return;
                }
            }
            respond(message, 481);
            return;
        }
        const auto id = str(message.header(h_From).uri().user());
        auto it = registrations_.find(id);
        if (it == registrations_.end() || it->second.expires <= epoch()
            || !sameSource(it->second.source, message.getSource())) {
            respond(message, 403);
            return;
        }
        if (method == OPTIONS) { respond(message, 200); return; }
        if (method != MESSAGE) { respond(message, 405); return; }
        auto body = rawBody(message);
        if (body.empty() || body.size() > MaxBody) { respond(message, 413); return; }
        respond(message, 200);
        emit({{"type", "message"}, {"device_id", id},
            {"body_base64", str(body.base64encode())}});
    }

    Json invite(const Json& command) {
        const auto id = command.at("session_id").get<std::string>();
        const auto device = command.at("device_id").get<std::string>();
        const auto channel = command.at("channel_id").get<std::string>();
        const auto sdp = command.at("sdp").get<std::string>();
        if (!std::regex_match(id, std::regex("[a-f0-9]{32}")) || !isId(channel) || sdp.size() > 65536)
            throw ApiError(400, "Invalid INVITE");
        auto existing = sessions_.find(id);
        if (existing != sessions_.end())
            return Json{{"call_id", str(existing->second.invite->header(h_CallId).value())}};
        if (sessions_.size() >= 2048) throw ApiError(503, "Session limit reached");
        const auto& registration = registered(device);
        auto message = request(channel, registration, INVITE);
        message->header(h_Subject).value() = data(channel + ":" + command.at("ssrc").get<std::string>()
            + "," + config_.at("sip_id").get<std::string>() + ":0");
        message->setContents(std::make_unique<PlainContents>(data(sdp), Mime("application", "sdp")));
        const auto callId = str(message->header(h_CallId).value());
        Session session;
        session.id = id;
        session.device = device;
        session.source = registration.source;
        session.deadline = Clock::now() + std::chrono::seconds(config_.value("invite_timeout", 15));
        session.invite = std::move(message);
        stack_.sendTo(*session.invite, session.source);
        sessions_.emplace(id, std::move(session));
        return Json{{"call_id", callId}};
    }
    std::unique_ptr<SipMessage> dialogRequest(Session& session, const SipMessage& answer, MethodTypes method) {
        NameAddr target = session.invite->header(h_To);
        if (answer.exists(h_Contacts) && !answer.header(h_Contacts).empty()) target = answer.header(h_Contacts).front();
        auto message = std::unique_ptr<SipMessage>(Helper::makeRequest(target, from_, contact_, method));
        message->header(h_From) = session.invite->header(h_From);
        message->header(h_To) = answer.header(h_To);
        message->header(h_CallId) = session.invite->header(h_CallId);
        message->header(h_CSeq).sequence() = session.invite->header(h_CSeq).sequence() + (method == BYE ? 1 : 0);
        if (answer.exists(h_RecordRoutes)) {
            for (const auto& route : answer.header(h_RecordRoutes)) message->header(h_Routes).push_front(route);
            // RFC 3261 strict-routing compatibility.
            if (!message->header(h_Routes).empty() && !message->header(h_Routes).front().uri().exists(p_lr)) {
                message->header(h_RequestLine).uri() = message->header(h_Routes).front().uri();
                message->header(h_Routes).pop_front();
                message->header(h_Routes).push_back(target);
            }
        }
        return message;
    }
    void sendDialog(Session& session, const SipMessage& answer, MethodTypes method) {
        auto message = dialogRequest(session, answer, method);
        if (answer.exists(h_RecordRoutes) && !answer.header(h_RecordRoutes).empty()) stack_.send(*message);
        else stack_.sendTo(*message, session.source);
    }
    void finish(Session& session, const std::string& state, const std::string& reason) {
        if (session.state == "failed" || session.state == "ended") return;
        session.state = state;
        session.retainUntil = Clock::now() + std::chrono::seconds(64);
        emit({{"type", "session"}, {"session_id", session.id}, {"state", state}, {"reason", reason}});
    }
    void sendCancel(Session& session) {
        if (session.provisional && !session.cancelSent) {
            stack_.sendTo(std::unique_ptr<SipMessage>(Helper::makeCancel(*session.invite)), session.source);
            session.cancelSent = true;
        }
    }
    void terminate(Session& session) {
        session.cancelled = true;
        if (session.answer && !session.byeSent) {
            sendDialog(session, *session.answer, BYE);
            session.byeSent = true;
        } else if (!session.answer) sendCancel(session);
        finish(session, "ended", "Session stopped");
    }
    void onResponse(const SipMessage& message) {
        const auto method = message.header(h_CSeq).method();
        if (method != INVITE) return;
        for (auto& item : sessions_) {
            auto& session = item.second;
            if (session.invite->header(h_CallId).value() != message.header(h_CallId).value()) continue;
            if (message.isFromWire() && !sameSource(session.source, message.getSource())) return;
            if (session.invite->header(h_From).param(p_tag) != message.header(h_From).param(p_tag)) return;
            const auto code = message.header(h_StatusLine).statusCode();
            session.invite->header(h_Vias) = message.header(h_Vias);
            if (code < 200) {
                session.provisional = true;
                if (session.cancelled) sendCancel(session);
                return;
            }
            if (code >= 300) { finish(session, "failed", "SIP " + std::to_string(code)); return; }
            if (!message.header(h_To).exists(p_tag)) { finish(session, "failed", "Missing dialog tag"); return; }
            // Every retransmitted/forked successful response needs its own ACK.
            sendDialog(session, message, ACK);
            if (session.answer && session.answer->header(h_To).param(p_tag) != message.header(h_To).param(p_tag)) {
                sendDialog(session, message, BYE);
                return;
            }
            if (!session.answer) session.answer = std::make_unique<SipMessage>(message);
            if (session.cancelled || session.state == "failed" || session.state == "ended") {
                if (!session.byeSent) { sendDialog(session, message, BYE); session.byeSent = true; }
                return;
            }
            if (session.state == "established") return;
            const auto sdp = str(rawBody(message));
            if (sdp.size() > 65536 || sdp.find_first_not_of("\r\n\t !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~") != std::string::npos) {
                finish(session, "failed", "Invalid SDP encoding");
                terminate(session);
                return;
            }
            session.state = "established";
            emit({{"type", "session"}, {"session_id", session.id}, {"state", "established"},
                {"sdp", sdp}});
            return;
        }
    }
    void tick() {
        const auto now = epoch();
        for (auto it = registrations_.begin(); it != registrations_.end();) {
            if (it->second.expires <= now) { disconnect(it->first); it = registrations_.erase(it); }
            else ++it;
        }
        for (auto it = replay_.begin(); it != replay_.end();) {
            if (it->second.second <= now) it = replay_.erase(it); else ++it;
        }
        for (auto it = sessions_.begin(); it != sessions_.end();) {
            auto& session = it->second;
            if (session.state == "inviting" && Clock::now() >= session.deadline) {
                session.cancelled = true;
                sendCancel(session);
                finish(session, "failed", "INVITE timed out");
            }
            if (Clock::now() >= session.retainUntil) it = sessions_.erase(it); else ++it;
        }
    }
};

int main(int argc, char** argv) {
    if (argc != 3 || std::string(argv[1]) != "--config") {
        std::cerr << "Usage: gb28181-sip --config <runtime.json>\n";
        return 2;
    }
    try {
        Log::initialize(Log::Cout, Log::Err, "gb28181-sip");
        Helper::setNonceHelper(new SourceNonceHelper());
        std::signal(SIGINT, [](int) { interrupted = true; });
        std::signal(SIGTERM, [](int) { interrupted = true; });
        std::ifstream stream(argv[2]);
        if (!stream) throw std::runtime_error("Cannot read service config");
        auto config = Json::parse(stream);
        const char* token = std::getenv("GB28181_INTERNAL_TOKEN");
        Service service(config, token ? token : "");
        service.run();
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "GB28181 startup failed: " << error.what() << '\n';
        return 1;
    }
}
