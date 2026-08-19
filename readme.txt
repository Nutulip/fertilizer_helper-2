readme_content = """# WUR Greenhouse Crop Nutrition EDSS (瓦赫宁根大学设施园艺营养决策支持系统)

[![GitHub Repository](https://img.shields.io/badge/GitHub-Repository-blue?logo=github)](https://github.com/Nutulip/fertilizer_helper-2)
[![Live Demo on Render](https://img.shields.io/badge/Live%20Demo-Render-green?logo=render)](https://fertilizer-helper.onrender.com/)

## 📖 项目简介 (Project Overview)

本项目是基于荷兰**瓦赫宁根大学与研究中心 (Wageningen University & Research, WUR)** 设施园艺无土栽培水肥金标准（如《Nutrient Solutions for Greenhouse Crops》）所开发的轻量化**平民化农艺专家决策支持系统 (Expert Decision Support System, EDSS)**。

系统采用**双驱混合控制架构 (Dual-Driven Hybrid Architecture)**：
1. **硬控制 / 确定性农艺熔断引擎 (Deterministic Agronomic Rules Engine)**：
   - 面向根际理化输入（$pH$、$EC$、阳离子/阴离子浓度如 $\\text{Ca}^{2+}$, $\\text{K}^+$, $\\text{NO}_3^-$ 等），使用硬编码条件分支（If-Else Nodes）锁死绝对安全红线。
   - 当检测到极端逆境指标（如 $pH < 5.2$ 或 $EC > 4.5\\text{ mS/cm}$）时，系统自动绕过大语言模型，直接输出标定的洗盐/调酸指令与精确纠偏步长（$\\text{mmol/L}$），彻底杜绝计算幻觉并避免算力浪费。
2. **柔性推理与知识转译层 (Flexible LLM Reasoning & Knowledge Translation)**：
   - 当指标处于安全振荡区间但存在微观偏离时，解算事实投喂给大模型，结合马尔德图表 (Mulder's Chart) 展开多因果生理分析与通俗易懂的诊断解释。
3. **8 大核心农艺模块 & 双语对照 (Bilingual Display)**：
   - 完美融合原水硬度扣除、A/B 母液配制、物候期 Crop Steering 控水控肥、排液比 (Leaching Fraction, LF) 动态洗盐等 8 大核心模块。
   - 全程严格遵循中英双语对照 (Bilingual Display) 规则。
   - 内置 PDF 智能过滤规则，能够自动识别并忽略非相关广告与图文干扰。

---

## 🖼️ 运行效果截图 (Demo Screenshot)

> 💡 *提示：请在项目根目录下创建 `docs/` 文件夹并将您的本地运行截图命名为 `screenshot.png` 存放于其中，下方的图片链接将自动生效。*

![WUR Fertilizer Helper Demo Screenshot](docs/screenshot.png)

🌐 **云端演示版 (Live Demo)**: [https://fertilizer-helper.onrender.com/](https://fertilizer-helper.onrender.com/)  
📦 **GitHub 源代码仓库 (GitHub Repo)**: [https://github.com/Nutulip/fertilizer_helper-2](https://github.com/Nutulip/fertilizer_helper-2)

---

## 🛠️ 技术栈 (Tech Stack)

* **后端框架 (Backend)**: FastAPI (Python 3.9+)
* **Web 服务器 (ASGI Server)**: Uvicorn
* **数据校验 (Data Validation)**: Pydantic v2
* **前端 (Frontend)**: HTML5 + CSS3 + JavaScript (单页响应式双语界面)
* **云端部署 (Deployment)**: Render Web Service (支持 PORT 环境变量自动识别与 CORS 跨域)

---

## 🚀 本地快速启动指南 (Local Setup Guide)

请按照以下步骤在本地搭建开发环境并启动服务：

### 1. 克隆代码仓库 (Clone Repository)