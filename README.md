# Delogo

Delogo 是一款基于人工智能的高效、精准的批量去水印工具。它采用了现代化的前后端分离架构，前端使用 Vue 3 + Vite + Electron 构建桌面级原生体验，后端由 FastAPI 驱动，借助先进的深度学习图像修复引擎 (`iopaint` + `big-lama`) 自动消除图片中的水印。

## 🌟 核心特性

- **极致纯净的画布体验**：支持拖拽导入单张或批量图片。
- **自适应比例框选**：通过拖拽绘制矩形框定位水印。系统自动采用**相对百分比坐标系**，不管原图分辨率如何，只要水印在画面的相对位置一致（例如都在右下角），只需在第一张图框选一次，即可完美适配所有同批次图片。
- **本地高性能 AI 处理**：集成了 LaMa (Resolution-robust Large Mask Inpainting) 深度学习模型，通过纯本地的推理运算，实现像素级的无痕去水印。
- **全自动批量处理流**：
  - 前端实时 WebSocket 推送处理进度与状态。
  - 完成后，提供沉浸式的 `Before & After` 对比滑块，滑动即可见证去水印前后的惊艳效果。

## 🏗️ 架构说明

- **Frontend (前端)**
  - 技术栈：Vue 3 + TypeScript + Vite + TailwindCSS
  - 容器环境：Electron (支持原生本地文件读写与原生弹窗选择夹)
  - 通信机制：HTTP 提交任务 + WebSocket 获取进度推送
- **Backend (后端)**
  - 技术栈：Python 3.12 + FastAPI + Uvicorn
  - 核心算法库：`iopaint` (LaMa 模型) + OpenCV (`cv2`)
  - 硬件加速支持：支持在 Mac 系统上调用 `mps` 苹果芯片加速框架。

## 🚀 启动指引

项目内置了一键启动脚本 `start_dev.sh`：

```bash
chmod +x start_dev.sh
./start_dev.sh
```

- 该脚本会自动激活 Python 虚拟环境，在 `61134` 端口启动 FastAPI 后端。
- 随后会自动启动前端的 Vite 开发服务器与 Electron 窗口。

## 📅 ROADMAP

详见 [ROADMAP.md](./ROADMAP.md)。项目未来将支持：
- 复杂形状的高级多边形画笔选区。
- 多水印同时去除支持。
- 更高级的掩码算法融合。
