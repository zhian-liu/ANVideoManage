import { useEffect, useState, useRef } from 'react';
import { Card, Col, Row, Table, Tag, Typography, Progress } from 'antd';
import {
  VideoCameraOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

import * as api from '../api';
import type { Device } from '../api/types';
import { useTheme } from '../theme/ThemeProvider';
import { useCountUp, useInView } from '../hooks/useAnimations';

export default function Dashboard() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const { theme } = useTheme();

  const statsRef = useRef<HTMLDivElement>(null);
  const isStatsInView = useInView(statsRef);

  useEffect(() => {
    setLoading(true);
    api.listDevices()
      .then(setDevices)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const online = devices.filter((d) => d.status === 'online').length;
  const offline = devices.filter((d) => d.status === 'offline').length;
  const onlineRate = devices.length > 0 ? Math.round((online / devices.length) * 100) : 0;

  // 数字动画
  const animatedTotal = useCountUp(devices.length, 1200);
  const animatedOnline = useCountUp(online, 1200);
  const animatedOffline = useCountUp(offline, 1200);
  const animatedRate = useCountUp(onlineRate, 1200);

  return (
    <div>
      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }} ref={statsRef}>
        <Col xs={24} sm={12} lg={6}>
          <Card
            bordered={false}
            className={`card-3d elevated-card slide-in-up ${isStatsInView ? '' : ''}`}
            style={{
              background: `linear-gradient(135deg, ${theme.primary.main}15 0%, ${theme.primary.main}05 100%)`,
              borderRadius: 12,
              border: `1px solid ${theme.border.default}`,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div style={{ color: theme.text.secondary, fontSize: 14, marginBottom: 8 }}>
                  设备总数
                </div>
                <div style={{
                  fontSize: 32,
                  fontWeight: 700,
                  color: theme.text.primary,
                  letterSpacing: -1,
                  fontVariantNumeric: 'tabular-nums',
                }}>
                  {loading ? <span className="skeleton" style={{ display: 'inline-block', width: 60, height: 40, borderRadius: 8 }}></span> : animatedTotal}
                </div>
              </div>
              <div
                className="scale-pulse"
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: 12,
                  background: theme.primary.dim,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 24,
                  color: theme.primary.main,
                }}
              >
                <VideoCameraOutlined />
              </div>
            </div>
          </Card>
        </Col>

        <Col xs={24} sm={12} lg={6}>
          <Card
            bordered={false}
            className="card-3d elevated-card slide-in-up delay-100"
            style={{
              background: `linear-gradient(135deg, ${theme.status.success}15 0%, ${theme.status.success}05 100%)`,
              borderRadius: 12,
              border: `1px solid ${theme.border.default}`,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div style={{ color: theme.text.secondary, fontSize: 14, marginBottom: 8 }}>
                  在线设备
                </div>
                <div style={{
                  fontSize: 32,
                  fontWeight: 700,
                  color: theme.status.success,
                  letterSpacing: -1,
                  fontVariantNumeric: 'tabular-nums',
                }}>
                  {loading ? <span className="skeleton" style={{ display: 'inline-block', width: 60, height: 40, borderRadius: 8 }}></span> : animatedOnline}
                </div>
              </div>
              <div
                className="bounce"
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: 12,
                  background: `${theme.status.success}15`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 24,
                  color: theme.status.success,
                }}
              >
                <CheckCircleOutlined />
              </div>
            </div>
          </Card>
        </Col>

        <Col xs={24} sm={12} lg={6}>
          <Card
            bordered={false}
            className="card-3d elevated-card slide-in-up delay-200"
            style={{
              background: `linear-gradient(135deg, ${theme.status.error}15 0%, ${theme.status.error}05 100%)`,
              borderRadius: 12,
              border: `1px solid ${theme.border.default}`,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div style={{ color: theme.text.secondary, fontSize: 14, marginBottom: 8 }}>
                  离线设备
                </div>
                <div style={{
                  fontSize: 32,
                  fontWeight: 700,
                  color: theme.status.error,
                  letterSpacing: -1,
                  fontVariantNumeric: 'tabular-nums',
                }}>
                  {loading ? <span className="skeleton" style={{ display: 'inline-block', width: 60, height: 40, borderRadius: 8 }}></span> : animatedOffline}
                </div>
              </div>
              <div
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: 12,
                  background: `${theme.status.error}15`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 24,
                  color: theme.status.error,
                }}
              >
                <CloseCircleOutlined />
              </div>
            </div>
          </Card>
        </Col>

        <Col xs={24} sm={12} lg={6}>
          <Card
            bordered={false}
            className="card-3d elevated-card slide-in-up delay-300"
            style={{
              background: `linear-gradient(135deg, ${theme.accent.main}15 0%, ${theme.accent.main}05 100%)`,
              borderRadius: 12,
              border: `1px solid ${theme.border.default}`,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ flex: 1 }}>
                <div style={{ color: theme.text.secondary, fontSize: 14, marginBottom: 8 }}>
                  在线率
                </div>
                <div style={{
                  fontSize: 32,
                  fontWeight: 700,
                  color: theme.accent.main,
                  letterSpacing: -1,
                  fontVariantNumeric: 'tabular-nums',
                  marginBottom: 8,
                }}>
                  {loading ? <span className="skeleton" style={{ display: 'inline-block', width: 80, height: 40, borderRadius: 8 }}></span> : `${animatedRate}%`}
                </div>
                {!loading && (
                  <Progress
                    percent={animatedRate}
                    strokeColor={theme.accent.main}
                    showInfo={false}
                    strokeWidth={6}
                    className="progress-animate"
                  />
                )}
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      {/* 设备列表 */}
      <Card
        title={
          <span style={{ fontSize: 16, fontWeight: 600, color: theme.text.primary }}>
            设备列表
          </span>
        }
        bordered={false}
        className="card-3d slide-in-up delay-400"
        style={{
          background: theme.bg.elevated,
          borderRadius: 12,
          border: `1px solid ${theme.border.default}`,
        }}
      >
        <Table
          rowKey="id"
          dataSource={devices}
          loading={loading}
          pagination={{ pageSize: 10, showSizeChanger: false }}
          style={{
            background: 'transparent',
          }}
          rowClassName={() => 'table-row-hover'}
          columns={[
            {
              title: '名称',
              dataIndex: 'name',
              render: (text: string) => (
                <span style={{ fontWeight: 500, color: theme.text.primary }}>{text}</span>
              ),
            },
            {
              title: '厂商',
              dataIndex: 'vendor',
              render: (text: string) => (
                <span style={{ color: theme.text.secondary }}>{text}</span>
              ),
            },
            {
              title: '接入方式',
              dataIndex: 'access_type',
              render: (v: string) => (
                <Tag
                  className="shine"
                  color={theme.primary.main}
                  style={{
                    borderRadius: 6,
                    border: 'none',
                    background: theme.primary.dim,
                    color: theme.primary.main,
                  }}
                >
                  {v === 'onvif' ? 'RTSP/ONVIF' : v}
                </Tag>
              ),
            },
            {
              title: 'IP 地址',
              dataIndex: 'ip',
              render: (v: string) => (
                <code
                  style={{
                    padding: '4px 8px',
                    borderRadius: 4,
                    background: theme.bg.hover,
                    color: theme.text.secondary,
                    fontSize: 13,
                    fontFamily: 'Monaco, Consolas, monospace',
                  }}
                >
                  {v || '-'}
                </code>
              ),
            },
            {
              title: '状态',
              dataIndex: 'status',
              render: (s: string) => {
                const isOnline = s === 'online';
                return (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className={`status-indicator ${isOnline ? 'status-online' : 'status-offline'}`}></span>
                    <span style={{
                      color: isOnline ? theme.status.success : theme.text.tertiary,
                      fontWeight: 500,
                    }}>
                      {isOnline ? '在线' : '离线'}
                    </span>
                  </div>
                );
              },
            },
            {
              title: '操作',
              render: (_) => (
                <Typography.Link
                  onClick={() => navigate('/live')}
                  className="ripple"
                  style={{
                    color: theme.primary.main,
                    fontWeight: 500,
                    padding: '4px 12px',
                    borderRadius: 6,
                    transition: 'all 0.25s',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = theme.primary.dim;
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'transparent';
                  }}
                >
                  实时预览 →
                </Typography.Link>
              ),
            },
          ]}
        />
      </Card>
    </div>
  );
}
