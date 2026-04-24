# MediaCoverGenerator

给 Emby 媒体库自动生成封面的独立服务。

这个项目已经不再依赖 MoviePilot，可以单独运行。  
它适合放在 NAS 上长期运行，也适合用 `docker compose` 部署。

如果你只是想尽快用起来，直接看下面这几段：

- `1. 这项目能干什么`
- `2. 最推荐的安装方式`
- `3. 第一次打开后怎么设置`
- `4. 怎么让它自动运行`

## 1. 这项目能干什么

它主要做 4 件事：

1. 读取 Emby 媒体库里的内容。
2. 根据你选的风格生成媒体库封面。
3. 把生成好的封面回写到 Emby。
4. 按你的设置自动执行。

支持的使用方式：

- 手动点按钮生成
- 按定时任务自动生成
- 通过 Emby Webhook 在新片入库后自动更新
- 给某个媒体库放本地素材图，直接拿本地图生成

## 2. 最推荐的安装方式

最推荐：`Docker Compose`

原因很简单：

- 最省事
- 适合 NAS
- 升级方便
- 配置和历史都会保存在 `data/` 目录里
- 默认直接拉现成镜像，不需要你在 NAS 本地慢慢 build

### 2.1 准备环境

你需要先准备好：

- 一台能运行 Docker 的机器或 NAS
- 已安装 `docker` 和 `docker compose`
- 一个可正常访问的 Emby
- Emby 的 API Key

### 2.2 启动项目

进入项目目录后执行：

```bash
docker compose up -d
```

第一次启动会做这些事：

- 从 GHCR 拉取已经发布好的镜像
- 启动容器
- 监听 `38100` 端口
- 自动创建 `data/` 目录

启动成功后，打开浏览器访问：

```text
http://你的NAS_IP:38100/
```

默认端口就是 `38100`。

## 3. 第一次打开后怎么设置

第一次打开页面后，按下面顺序做就行。

### 3.1 填基础设置

你至少要填这两项：

- `Emby 服务地址`
- `Emby API Key`

示例：

```text
Emby 服务地址：http://192.168.1.100:8096
```

`API Key` 获取方式：

1. 打开 Emby 后台
2. 找到 API Key / 高级 / 开发者相关页面
3. 创建或复制一个可用的 Key

填完后点击页面右下角的 `保存设置`。

### 3.2 选择媒体库

保存后，页面会读取 Emby 里的媒体库。

你可以：

- 勾选要生成封面的媒体库
- 给每个媒体库单独设置主标题
- 给每个媒体库单独设置副标题

建议：

- 电影库填：`电影 / MOVIES`
- 剧集库填：`剧集 / TV`
- 成人库、纪录片库、自制库都可以分别设置自己的标题

如果你不改，默认会直接用媒体库名称。

### 3.3 选择封面风格

在 `封面风格` 面板里可以选择：

- 静态风格
- 动态风格

新手建议先用：

- 静态风格
- 默认字体
- 默认分辨率

先确认整条链路能跑通，再去调整进阶参数。

### 3.4 手动生成一次试试

点击页面右下角的：

```text
生成封面
```

然后去 `任务管理` 页面看进度。

生成成功后，你就能在 Emby 里看到新的媒体库封面。

## 4. 怎么让它自动运行

这个项目有两种自动方式。

### 4.1 定时任务

适合：

- 每天凌晨自动更新一次
- 每周更新一次
- 不关心实时入库，只想定时重做封面

页面里打开：

- `定时更新`

再填写 cron 表达式，例如：

```text
0 3 * * *
```

含义：

- 每天凌晨 3 点执行一次

保存后，容器常驻运行时就会自动按计划执行。

### 4.2 Emby 入库监控

适合：

- 新电影入库后自动更新电影库封面
- 新剧集入库后自动更新剧集库封面

页面里打开：

- `入库监控`

然后设置：

- `入库延迟（秒）`

建议先用：

```text
60
```

意思是：

- Emby 通知来了以后，先等 60 秒再生成
- 避免文件刚入库、元数据还没完全刷新时就立刻执行

然后把页面上显示的 `Webhook 地址` 填到 Emby 的 Webhook 插件里。

示例：

```text
http://你的NAS_IP:38100/webhooks/emby
```

Emby Webhook 里建议只勾选：

```text
library.new
```

## 5. 飞牛 / NAS 最省事的用法

如果你用飞牛，推荐这样做：

1. 把项目放到固定目录
2. 在这个目录里执行 `docker compose up -d`
3. 打开 `http://你的NAS_IP:38100/`
4. 填一次 Emby 配置并保存
5. 开启 `定时更新` 或 `入库监控`

这样以后基本就不用再手工进容器折腾了。

### 5.1 更新版本

代码更新后，在项目目录执行：

```bash
docker compose pull
docker compose up -d
```

### 5.2 停止服务

```bash
docker compose down
```

### 5.3 重启服务

```bash
docker compose restart
```

### 5.4 查看日志

```bash
docker compose logs -f
```

### 5.5 如果你非要本地构建

默认不需要。

如果你确实想自己在本地构建镜像，可以用：

```bash
docker compose -f compose.yaml -f compose.build.yaml up -d --build
```

## 6. `data/` 目录是干什么的

这个目录非常重要。

你在页面里保存的设置、生成历史、本地素材目录，都会在这里。

常见内容说明：

- `data/config.json`
  这是主配置文件
- `data/input/`
  这里放你手动准备的素材图
- `data/cache/`
  运行时缓存的图片
- `data/recent_covers/`
  最近生成的封面备份
- `data/fonts/`
  你自己额外放的字体

### 6.1 本地素材怎么放

如果你不想完全依赖 Emby 抓图，也可以自己准备素材图。

目录格式：

```text
data/input/媒体库名/
```

例如：

```text
data/input/电影/1.jpg
data/input/电影/2.jpg
data/input/电影/3.jpg
```

只要媒体库名对得上，这个媒体库就会优先用你放进去的图片。

## 7. 手动运行方式

如果你不用 Docker，也可以直接运行 Python 版。

### 7.1 安装依赖

```bash
pip install -r requirements.txt
```

### 7.2 启动 Web 服务

```bash
python -m mediacovergenerator
```

打开：

```text
http://127.0.0.1:38100/
```

### 7.3 只跑一次就退出

如果你只是想让 NAS 的计划任务“拉起来跑一次然后退出”，可以这样：

```bash
python -m mediacovergenerator --run-once
```

这个命令会：

- 读取 `data/config.json`
- 按你已经保存的设置执行一次
- 运行结束后退出

适合：

- 不想让服务常驻
- 完全交给 NAS 自己的计划任务系统

## 8. 页面里三个标签页分别是干什么的

### 8.1 设置

这里是日常主要操作区。

里面有三块：

- `基础设置`
- `媒体库`
- `封面风格`

### 8.2 任务管理

这里看当前任务和历史任务状态。

你可以：

- 看任务是否在运行
- 看开始时间、结束时间
- 取消正在运行的任务
- 删除已经完成或失败的任务记录

### 8.3 历史管理

这里看已经生成过的封面记录。

你可以：

- 查看历史图片
- 删除单条历史
- 批量删除历史
- 清空历史

## 9. 常见问题

### 9.1 为什么我每次重启后配置还在？

因为配置保存在：

```text
data/config.json
```

只要你挂载了 `./data:/app/data`，配置就会一直保留。

### 9.2 为什么页面里能生成，但 Emby 里还是旧封面？

常见原因：

- Emby 缓存还没刷新
- 你看的客户端页面还没重新加载
- 这次任务其实失败了，请去 `任务管理` 看错误

### 9.3 为什么动态封面本地是动的，Emby 里却是静态的？

这是 Emby 的限制，不是这个项目没生成成功。

目前 Emby 的媒体库主图在实际展示时，通常只显示首帧。  
也就是说：

- 本地文件可能是动图
- 上传到 Emby 后，Emby 端显示出来仍可能是静态图

如果你主要是给 Emby 媒体库用，建议优先使用静态风格。

### 9.4 为什么开启了入库监控，却没有自动生成？

请检查这几项：

1. 页面里是否已经开启 `入库监控`
2. Emby Webhook 地址是否填对
3. Emby Webhook 是否只勾选了 `library.new`
4. 这个媒体库是否在页面里被勾选
5. `入库延迟` 是否还没到

### 9.5 为什么媒体库没有显示出来？

通常是下面几种情况：

- Emby 地址填错了
- API Key 不对
- NAS 无法访问 Emby
- Emby 开了 HTTPS，但证书或地址配置有问题

先看页面顶部的连接状态提示。

### 9.6 删除 `data/config.json` 会怎样？

会恢复成“第一次使用”的状态。

也就是：

- 页面配置会被清空
- 下次启动后会重新生成默认配置文件

## 10. 端口、镜像、容器信息

默认端口：

```text
38100
```

`compose.yaml` 默认使用：

- 容器名：`mediacovergenerator`
- 镜像名：`ghcr.io/a39908646/mediacovergenerator:latest`

## 11. 项目目录说明

```text
MediaCoverGenerator/
├─ mediacovergenerator/      程序代码
├─ data/                     运行数据
├─ compose.yaml              Docker Compose 配置
├─ Dockerfile                Docker 镜像构建文件
└─ requirements.txt          Python 依赖
```

## 12. API 一览

普通用户其实不用关心这部分。  
如果你要自己对接，可以看这里：

- `GET /health`
- `GET /config`
- `PUT /config`
- `GET /libraries`
- `POST /jobs/generate`
- `POST /jobs/generate/{libraryId}`
- `GET /jobs`
- `POST /jobs/{jobId}/cancel`
- `DELETE /jobs/{jobId}`
- `POST /jobs/delete`
- `GET /history`
- `GET /history/{recordId}/image`
- `DELETE /history/{recordId}`
- `POST /history/delete`
- `DELETE /history`
- `POST /webhooks/emby`

## 13. 一句话建议

如果你是第一次用，最稳的顺序就是：

1. `docker compose up -d`
2. 打开页面
3. 填 Emby 地址和 API Key
4. 保存设置
5. 先手动生成一次
6. 确认 Emby 里显示正常
7. 再去开定时任务或入库监控
