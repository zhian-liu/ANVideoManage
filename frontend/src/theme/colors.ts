// 深色水墨主题：墨黑背景、黛青主色和宣纸色文字
export const darkTheme = {
  // 背景层级 - 从最深到最浅
  bg: {
    base: '#171917',      // 墨底
    elevated: '#222622',  // 砚台灰
    hover: '#2C322C',     // 悬停状态
    active: '#364036',    // 激活状态
    header: '#121512',    // 头部背景
  },
  // 主色 - 黛青
  primary: {
    main: '#A9C7BF',      // 主色
    hover: '#C7DDD5',     // 悬停
    active: '#89AEA4',    // 激活
    dim: 'rgba(169, 199, 191, 0.16)', // 半透明背景
  },
  // 辅助色 - 纸上印章的暖色
  accent: {
    main: '#D6B87C',
    hover: '#E4CEA1',
    dim: 'rgba(214, 184, 124, 0.14)',
  },
  // 文字颜色
  text: {
    primary: '#F3F0E7',
    secondary: '#BAC0B7',
    tertiary: '#899187',
    inverse: '#182019',
  },
  // 边框
  border: {
    default: 'rgba(206, 213, 201, 0.16)',
    hover: 'rgba(206, 213, 201, 0.28)',
  },
  // 状态色
  status: {
    success: '#91B6A5',
    warning: '#D2A96D',
    error: '#D28C86',
    info: '#A9C7BF',
  },
};

// 亮色水墨主题：宣纸白、墨绿和少量赭石
export const lightTheme = {
  bg: {
    base: '#F4F1E8',
    elevated: '#FBFAF5',
    hover: '#E8E7DD',
    active: '#D8DDD4',
    header: '#F7F5EE',
  },
  primary: {
    main: '#385B54',
    hover: '#2E4943',
    active: '#244039',
    dim: 'rgba(56, 91, 84, 0.12)',
  },
  accent: {
    main: '#A67C52',
    hover: '#8D6846',
    dim: 'rgba(166, 124, 82, 0.12)',
  },
  text: {
    primary: '#202520',
    secondary: '#566057',
    tertiary: '#7A8279',
    inverse: '#F8F5EA',
  },
  border: {
    default: '#CDD2C9',
    hover: '#B9C2B8',
  },
  status: {
    success: '#477A62',
    warning: '#A67C52',
    error: '#B45F59',
    info: '#385B54',
  },
};

export type Theme = typeof darkTheme;
