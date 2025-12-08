# 小智智控台移动版 (manager-mobile) 项目说明

## 项目概述

小智智控台移动版 (manager-mobile) 是一个基于 uni-app v3 + Vue 3 + Vite 的跨端移动管理端应用，支持 App（Android & iOS）和微信小程序。该项目是 xiaozhi-esp32-server 项目的移动端管理后台，为智能硬件设备提供移动管理功能。

该项目支持多平台开发，主要技术栈包括：
- **框架**: uni-app v3 + Vue 3
- **构建工具**: Vite
- **状态管理**: Pinia + pinia-plugin-persistedstate
- **UI 组件库**: wot-design-uni
- **网络请求**: alova + @alova/adapter-uniapp
- **样式**: UnoCSS
- **代码规范**: ESLint + Prettier + Husky + lint-staged

## 核心架构

### 服务组件
1. **路由管理**：基于 uni-app 的路由系统，包含路由拦截与权限验证
2. **网络请求**：基于 alova 的统一请求处理，包含认证与错误处理
3. **状态管理**：基于 pinia 的全局状态管理，支持数据持久化
4. **国际化**：支持多语言功能

### 主要功能模块
1. **用户认证**：登录验证、token 管理
2. **权限控制**：基于路由的登录验证拦截器
3. **数据管理**：状态持久化存储
4. **UI 组件**：响应式跨平台用户界面

## 项目结构

```
xiaozhi-esp32-server/main/manager-mobile/
├── env/                      # 环境变量配置目录
│   ├── .env                  # 默认环境变量
│   ├── .env.development      # 开发环境变量
│   ├── .env.production       # 生产环境变量
│   └── .env.test            # 测试环境变量
├── src/                      # 源代码目录
│   ├── api/                 # API 接口定义
│   ├── components/          # 通用组件
│   ├── hooks/               # Vue 组合式 API hooks
│   ├── http/                # HTTP 请求封装
│   ├── i18n/                # 国际化配置
│   ├── layouts/             # 页面布局组件
│   ├── pages/               # 页面文件
│   ├── pages-sub/           # 分包页面
│   ├── router/              # 路由配置
│   ├── static/              # 静态资源
│   ├── store/               # Pinia 状态管理
│   ├── style/               # 样式文件
│   ├── utils/               # 工具函数
│   ├── App.vue              # 应用主组件
│   ├── main.ts              # 应用入口文件
│   ├── manifest.json        # 应用配置文件
│   └── pages.json           # 页面路由配置
├── .env                     # 环境变量示例
├── .env.development         # 开发环境变量配置
├── .env.production          # 生产环境变量配置
├── favicon.ico              # 网站图标
├── index.html               # HTML 模板
├── manifest.config.ts       # 应用清单配置
├── pages.config.ts          # 页面路由配置
├── vite.config.ts           # Vite 构建配置
├── uno.config.ts            # UnoCSS 配置
├── package.json             # 项目依赖和脚本
└── README.md                # 项目说明文档
```

## 配置文件

- `env/` 目录：包含不同环境的环境变量配置文件
- `manifest.config.ts`：应用清单配置，包含多平台特定配置
- `pages.config.ts`：页面路由配置
- `vite.config.ts`：Vite 构建配置
- `uno.config.ts`：UnoCSS 样式配置

## 构建和运行

### 环境要求
- Node >= 18
- pnpm >= 7.30（建议使用项目中声明的 `pnpm@10.x`）
- 可选：HBuilderX（App 调试/打包）、微信开发者工具（微信小程序）

### 安装依赖
```bash
pnpm install
```

### 本地开发
- H5: `pnpm dev` 或 `pnpm dev:h5`，然后观察启动日志显示的 IP 端口号
- 微信小程序：`pnpm dev:mp` 或 `pnpm dev:mp-weixin`，然后用微信开发者工具导入 `dist/dev/mp-weixin`
- App：用 HBuilderX 导入项目，然后运行

### 环境变量与配置
项目使用自定义 `env` 目录存放环境文件，按 Vite 规范命名：`.env.development`、`.env.production` 等。

关键变量（部分）：
- `VITE_APP_TITLE`：应用名称（写入 `manifest.config.ts`）
- `VITE_UNI_APPID`：uni-app 应用 appid（App）
- `VITE_WX_APPID`：微信小程序 appid（mp-weixin）
- `VITE_FALLBACK_LOCALE`：默认语言，如 `zh-Hans`
- `VITE_SERVER_BASEURL`：服务端基础地址（HTTP 请求 baseURL）
- `VITE_DELETE_CONSOLE`：构建时是否移除 console（`true`/`false`）
- `VITE_SHOW_SOURCEMAP`：是否生成 sourcemap（默认关闭）
- `VITE_LOGIN_URL`：未登录跳转的登录页路径（路由拦截器使用）

## 主要依赖

- `@dcloudio/uni-app`：uni-app 核心框架
- `vue`：Vue 3 框架
- `pinia`：轻量级状态管理
- `alova`：现代化请求策略库
- `wot-design-uni`：UI 组件库
- `unocss`：原子化 CSS 引擎
- `typescript`：TypeScript 支持

## 开发约定

### 代码结构
- 页面路由由 `@uni-helper/vite-plugin-uni-pages` 与 `pages.config.ts` 统一生成
- 组件与 hooks 自动导入通过 `unplugin-auto-import` 与 `@uni-helper/vite-plugin-uni-components` 实现
- 样式使用 UnoCSS 与 `src/style/index.scss`
- 状态管理使用 Pinia + `pinia-plugin-persistedstate`

### 路由与鉴权
- 在 `src/main.ts` 中注册了路由拦截插件 `routeInterceptor`
- 黑名单拦截：仅对配置为需要登录的页面进行校验（来源 `@/utils` 的 `getNeedLoginPages`）
- 登录判断：基于用户信息（`pinia` 的 `useUserStore`），未登录将跳转到 `VITE_LOGIN_URL`，并附带重定向回原页面的参数

### 网络请求
- 基于 `alova` + `@alova/adapter-uniapp`，统一在 `src/http/request/alova.ts` 创建实例
- `baseURL` 读取环境配置（`getEnvBaseUrl`），可通过 `method.config.meta.domain` 动态切换域名
- 认证：默认从本地 `token`（`uni.getStorageSync('token')`）注入 `Authorization` 头，缺失则重定向登录
- 响应：统一处理 `statusCode !== 200` 的 HTTP 错误与业务 `code !== 0` 的错误；`401` 会清除 token 并跳转登录

### 构建与发布

#### 微信小程序
1. 确保已配置正确的 `VITE_WX_APPID`
2. 运行 `pnpm build:mp`，产物在 `dist/build/mp-weixin`
3. 用微信开发者工具导入项目目录，并上传代码
4. 在微信公众平台提交审核

#### Android & iOS App
1. 确保已配置正确的 `VITE_UNI_APPID`
2. 运行 `pnpm build:app`，产物在 `dist/build/app`
3. 用 HBuilderX 导入项目目录
4. 在 HBuilderX 中点击"发行" → "原生App-云打包"
5. 配置打包参数（应用图标、启动图、证书等）
6. 点击"打包"开始云打包流程

## 常用脚本

```bash
# 开发
pnpm dev:mp        # 等价 dev:mp-weixin
pnpm dev:app       # App 开发
pnpm dev:h5        # H5 开发

# 构建
pnpm build:mp      # 构建微信小程序
pnpm build:app     # 构建 App
pnpm build:h5      # 构建 H5

# 其他
pnpm type-check    # 类型检查
pnpm lint          # 代码检查
pnpm lint:fix      # 代码检查并修复
```

## 部署说明

1. 修改 `env/.env.production` 中的服务端地址 `VITE_SERVER_BASEURL` 为您的实际服务端地址
2. 更新 `VITE_UNI_APPID` (uni-app 应用 ID) 和 `VITE_WX_APPID` (微信小程序 ID)
3. 修改 `VITE_APP_TITLE` 为您的应用名称
4. 根据需要更新 `src/static/logo.png` 等图标资源
5. 检查 `manifest.config.ts` 中的应用配置信息
6. 运行对应平台的构建命令

## 维护者

该项目是 xiaozhi-esp32-server 项目的一部分，由华南理工大学刘思源教授团队主导研发。

## 许可证

本项目采用 MIT 许可证，详见 LICENSE 文件。