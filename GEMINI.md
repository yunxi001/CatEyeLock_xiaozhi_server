# GEMINI.md

## 项目概述

本项目 `xiaozhi-esp32-server` 是一个为 `xiaozhi-esp32` 开源智能硬件项目提供支持的综合性后端服务。它是一个多组件、多语言的系统，旨在提供人工智能驱动的功能，如语音交互、声纹识别和知识库集成。

该项目架构由四个主要部分组成：

1.  **核心AI/IoT服务器 (`main/xiaozhi-server/`):**
    *   **技术栈:** Python 3.10
    *   **功用:** 项目的中央神经系统。它负责与ESP32设备进行实时通信（通过MQTT、UDP、WebSocket），处理音频，与众多第三方及本地AI模型（LLM、ASR、TTS、VLLM）集成，并执行核心应用逻辑。

2.  **管理后台API (`main/manager-api/`):**
    *   **技术栈:** Java 21, Spring Boot 3
    *   **功用:** 为Web和移动管理界面提供RESTful API后端。它管理用户数据、设备配置和系统设置，将数据持久化到MySQL数据库，并使用Redis进行缓存。

3.  **Web控制面板 (`main/manager-web/`):**
    *   **技术栈:** Vue.js 2, Element-UI
    *   **功用:** 一个基于Web的管理仪表板（“智控台”），用于管理整个系统。它与 `manager-api` 进行交互。

4.  **移动端控制面板 (`main/manager-mobile/`):**
    *   **技术栈:** Vue.js 3, `uni-app`
    *   **功用:** 一个用于系统管理的跨平台移动应用程序，能够编译成iOS、Android和H5版本。

## 构建与运行

本项目可以通过Docker（推荐）进行完整部署，也可以从源码单独运行每个服务。

### Docker (全栈部署)

启动整个系统最简单的方式是使用 Docker Compose。

1.  **进入Python服务器目录:**
    ```shell
    cd main/xiaozhi-server
    ```

2.  **启动所有服务:**
    此命令将启动Python服务器、Java/Web容器、一个MySQL数据库和一个Redis实例。
    ```shell
    docker-compose -f docker-compose_all.yml up -d
    ```

### 从源码运行

#### 1. Python AI/IoT 服务器

*   **环境要求:** Python 3.10
*   **目录:** `main/xiaozhi-server/`
*   **安装依赖:**
    ```shell
    pip install -r requirements.txt
    ```
*   **运行:**
    ```shell
    python app.py
    ```

#### 2. Java 管理后台 API

*   **环境要求:** JDK 21, Maven
*   **目录:** `main/manager-api/`
*   **安装/构建:**
    ```shell
    mvn clean package
    ```
*   **运行:**
    ```shell
    java -jar target/xiaozhi-esp32-api.jar
    ```

#### 3. Vue.js Web 控制面板

*   **环境要求:** Node.js, npm
*   **目录:** `main/manager-web/`
*   **安装依赖:**
    ```shell
    npm install
    ```
*   **运行 (开发模式):**
    这将启动一个本地开发服务器。在生产环境中，`npm run build` 生成的静态文件通常由Java后端提供。
    ```shell
    npm run serve
    ```
*   **构建 (生产模式):**
    ```shell
    npm run build
    ```

#### 4. `uni-app` 移动端控制面板

*   **环境要求:** Node.js >= 18, pnpm
*   **目录:** `main/manager-mobile/`
*   **安装依赖:**
    ```shell
    pnpm install
    ```
*   **运行 (H5开发模式):**
    ```shell
    pnpm run dev:h5
    ```
*   **构建 (H5生产模式):**
    ```shell
    pnpm run build:h5
    ```

## 开发约定

*   **多语言技术栈:** 项目为不同任务选择了合适的工具：Python用于AI，Java用于构建稳健的企业级后端，Vue.js用于现代化的前端界面。
*   **配置管理:** 系统配置通过 `main/xiaozhi-server/` 目录下的 `.yaml` 文件进行管理。管理API遵循Spring标准的 `application.properties` 或 `application.yml`。
*   **包管理:** `manager-mobile` 项目强制使用 `pnpm` 进行包管理。
*   **API文档:** Java API 使用 `knife4j` 生成API文档，这是前端开发的重要参考资源。
*   **模块化:** 项目结构清晰，划分为不同的模块，允许独立开发和部署。`docker-compose_all.yml` 文件是理解这些模块在网络层面如何交互的最佳参考。