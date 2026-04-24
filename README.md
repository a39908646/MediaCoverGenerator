# MediaCoverGenerator

独立版媒体库封面生成服务，目标是摆脱对 MoviePilot 宿主的依赖，直接以 Web 服务运行。

当前仓库以独立版服务为主：

- `mediacovergenerator/`：新的独立服务实现
- `archive/`：已归档的旧插件代码和开发期辅助文件

## 功能范围

- Emby 媒体库读取
- 静态/动态封面生成
- 封面回写到 Emby
- 本地输入素材目录
- 配置管理 API
- 任务触发、状态查询、取消
- 最近生成历史

## 快速开始

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 启动服务

```bash
python -m mediacovergenerator
```

3. 打开管理页

```text
http://127.0.0.1:38100/
```

## 适合 NAS 的两种运行方式

### 方式 1：常驻服务 + 内置定时任务

适合群晖、威联通这类长期在线的 NAS。

1. 启动服务
2. 打开页面或编辑 [config.json](/C:/github_repo/MediaCoverGenerator/data/config.json)
3. 设置：
   - `schedule.enabled = true`
   - `schedule.cron = "0 3 * * *"` 这类 cron 表达式
4. 保存后服务会按计划自动执行

这种方式下不需要每次手工进目录执行命令，服务常驻即可。

### 方式 2：NAS 任务计划 + 一次性执行

如果你更喜欢让 NAS 自己定时拉起任务，可以直接调用：

```bash
python -m mediacovergenerator --run-once
```

它会：
- 读取现有 [config.json](/C:/github_repo/MediaCoverGenerator/data/config.json)
- 按 `selected_library_ids` 或全部媒体库执行一次
- 执行完成后退出

这更适合 NAS 的“计划任务 / 定时任务”模式。

## Docker 运行

仓库已经带了 [Dockerfile](/C:/github_repo/MediaCoverGenerator/Dockerfile)，可以直接构建：

```bash
docker build -t mediacovergenerator .
docker run -d \
  --name mediacovergenerator \
  -p 38100:38100 \
  -v /your/path/data:/app/data \
  -v /your/path/fonts:/app/fonts \
  mediacovergenerator
```

更推荐至少挂载 `/app/data`，这样配置、缓存和历史不会丢。

## Docker Compose

仓库已经带了 [compose.yaml](/C:/github_repo/MediaCoverGenerator/compose.yaml)，按飞牛这类直接使用 `docker compose` 的环境做了收口：

- 固定容器名：`mediacovergenerator`
- 固定镜像名：`mediacovergenerator:latest`
- 默认时区：`Asia/Shanghai`
- 日志自动滚动，避免容器日志无限增长
- `./data` 持久化到容器内 `/app/data`

启动：

```bash
docker compose up -d --build
```

停止：

```bash
docker compose down
```

更新后重建：

```bash
docker compose up -d --build
```

默认映射：

- Web 页面：`http://NAS_IP:38100/`
- 持久化目录：`./data -> /app/data`
- 容器时区：`Asia/Shanghai`

也就是说，下面这些内容都会保存在宿主机的 `data/` 里：

- 配置文件
- 字体缓存
- 图片缓存
- 最近生成历史
- 本地输入素材目录

如果你想在飞牛里直接编辑配置，主要看这个文件：

- [config.json](/C:/github_repo/MediaCoverGenerator/data/config.json)

如果你想给某个媒体库放本地素材图，放到：

- `data/input/<媒体库名>/`

例如：

```text
data/input/电影/1.jpg
data/input/电影/2.jpg
```

### 飞牛推荐用法

如果你准备在飞牛上长期运行，建议就按下面这套：

1. 把项目放到一个固定目录，例如：

```text
/vol1/docker/MediaCoverGenerator
```

2. 进入项目目录启动：

```bash
docker compose up -d --build
```

3. 打开：

```text
http://飞牛IP:38100/
```

4. 在页面里填一次 Emby 配置并保存

5. 开启“内置定时任务”，设置 cron，例如：

```text
0 3 * * *
```

后面就不需要再手工执行命令了，容器会常驻，服务自己按 cron 跑。

### 飞牛更新方式

代码更新后，在项目目录执行：

```bash
docker compose up -d --build
```

如果只是重启容器：

```bash
docker compose restart
```

查看日志：

```bash
docker compose logs -f
```

如果你准备用容器常驻运行，推荐：

1. `docker compose up -d --build`
2. 打开页面填一次 Emby 配置并保存
3. 开启“内置定时任务”
4. 设置 cron，例如 `0 3 * * *`

这样后面就不用再手工进目录执行命令了。

## Emby Webhook 入库监控

独立版已经支持基于 Emby Webhook 的入库监控，不再依赖 MoviePilot。

页面里可以配置：

- `入库监控`
- `入库延迟（秒）`
- `Webhook Token（可选）`

启用后，把页面显示的 `Webhook 地址` 配到 Emby 的 Webhook 插件里，并勾选 `library.new` 事件。

建议：

1. 打开 `入库监控`
2. 设置 `入库延迟（秒）`，默认 `60`
3. 填一个 `Webhook Token`
4. 把页面显示的 URL 配到 Emby Webhook
5. 在 Emby 里只勾选 `library.new`

示例：

```text
http://NAS_IP:38100/webhooks/emby?token=your-token
```

也可以不用 query 参数，把 token 放到请求头 `X-Webhook-Token`。

服务收到事件后会：

- 校验 token
- 解析新增条目属于哪个媒体库
- 延迟执行
- 只更新对应媒体库封面

如果页面里只勾选了部分媒体库，Webhook 也只会处理这些被选中的媒体库。

## 首版 API

- `GET /health`
- `GET /config`
- `PUT /config`
- `GET /libraries`
- `POST /jobs/generate`
- `POST /jobs/generate/{libraryId}`
- `POST /jobs/{jobId}/cancel`
- `GET /jobs`
- `GET /history`
- `POST /webhooks/emby`

## 目录说明

- `mediacovergenerator/assets/fonts/`：默认字体资源
- `mediacovergenerator/assets/images/`：风格预览和静态资源
- `mediacovergenerator/style/`：复用后的封面风格逻辑
- `mediacovergenerator/utils/`：复用后的图像和网络工具
- `data/`：运行期配置、缓存、历史和最近封面输出
- `archive/`：旧 MoviePilot 插件实现和开发期测试，当前运行不依赖
