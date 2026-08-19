# 桌面猫咪挂件 —— 项目 TODOLIST

按里程碑推进，完成一个打一个勾（并在对话里告诉你进度）。

## 里程碑 1：素材准备 ✅（已完成）
- [x] 找到可用的猫咪 PNG 素材（MIT 授权，1ilit/Desktop-Cat 像素猫）
- [x] 裁剪成统一画布并放入 `assets/cat/`
- [x] 生成"眨眼 / 被撸"占位帧（`scripts/make_placeholder_frames.py`）

## 里程碑 2：项目骨架与主程序 ✅（已完成）
- [x] `main.py`：无边框置顶透明窗口 + 拖拽 + 单击交互
- [x] 五套动画：发呆 / 眨眼 / 走路 / 被撸 / 睡觉
- [x] 自动游走 + 碰壁转向 + 右键菜单（暂停走动 / 睡觉 / 退出）
- [x] 素材路径变量与 `ANIM_CONFIG` 集中配置，注释详尽

## 里程碑 3：本地运行验证 ✅（已完成）
- [x] 语法检查通过
- [x] 状态机逻辑测试通过（走路转向、点击被撸、暂停、睡觉/唤醒、自动入睡）

## 里程碑 4：替换成你自己的猫咪 ✅（已完成）
- [x] 5 张照片（HEIC）转 PNG
- [x] rembg AI 抠图（`previews/cutout_preview.png` 已确认干净）
- [x] 生成五态帧并替换 `assets/cat/`（22 帧，256x256）
- [x] 主程序逻辑测试通过（新素材）
- [x] 在你电脑上实机跑通（用 `.venv314/bin/python main.py`，Tk 9.0 修复显示问题）

## 里程碑 4.5：视频走路帧 ✅（已完成）
- [x] 5s 猫咪走路视频（`input_photos/走路.mp4`）抽帧 61 张
- [x] u2net 逐帧抠图（对比 isnet 后用户选定 u2net）
- [x] 按用户选定只保留 walk_37~44（一个猫步），重排为 `walk_1~8.png`
- [x] 更新帧数配置（8 帧，83ms/帧）
- [x] 重新生成动图预览 `previews/walk_animation.gif`
- [ ] 实机确认一个猫步循环自然度

## 里程碑 4.6：被抚摸 / 发呆 / 睡觉 三套视频动作 ✅（已完成，待实机验收）
- [x] 全帧率抽取（24fps，每视频 121 帧，共 363 帧，不抽稀）
- [x] u2net 逐帧抠图 363 张
- [x] 任务 A：qwen3.5:9b 逐帧判定全部 363 帧（可用率 95~108/121）
- [x] 任务 B：最终动画组合经 qwen 三轮验收（结论：连续帧方案已到物理极限，qwen 仍判不合格，报告已注明）
- [x] 生成连续帧动画：idle 8 / pet 8 / sleep 10，统一裁剪框 256x256
- [x] 更新 main.py 配置 + 预览图 + 验收报告（previews/qwen_report.md）
- [ ] 醒来后实机确认三套动作效果，不满意可换帧重生成

## 里程碑 4.7：Q 版卡通素材 ✅（已完成，待实机验收）
- [x] 安装 qwen-image-edit 技能并配置 DashScope API Key
- [x] 以用户提供的 pet_1/sleep_4 为形象参考，生成正面发呆 + 侧面走路
- [x] 修复走路图缺失眼睛问题（qwen_walk_v2）
- [x] rembg 抠图 + 生成五态动画（idle8/blink4/walk8/pet8/sleep10）替换 assets/cat
- [x] 逻辑测试通过，预览图/GIF 已生成（previews/q_*.png, q_*.gif）
- [ ] 实机确认 Q 版动画效果
- [ ] 重新打包 Windows exe（需要有效 GitHub token 或网页手动触发 Actions）

## 里程碑 6：配置化 + 远程更新 ✅（代码完成，待推送/打包）
- [x] `config.json`：states（动作）/ menu（右键菜单）/ behavior（行为）/ remote（远程源）
- [x] main.py：菜单按配置生成，动作帧数/速度按配置加载
- [x] 素材远程拉取 + 本地缓存 + 离线回退
- [x] 配置系统逻辑测试通过（含远程失败回退）
- [ ] 仓库改为公开 + 推送 config.json/素材 + 重新打包 exe

## 里程碑 5：打包 Windows exe ⏳（需要一台 Windows 电脑）
- [x] 方案 A：GitHub Actions 云端打包（仓库 caluo123/cat-desktop-pet）
- [x] `dist/CatPet.exe`（19.5MB）已生成并下载到本地
- [ ] 在真实 Windows 上双击验证动画与透明效果
- [ ] （可选）把 exe 发给朋友 / 放到桌面双击自用

## 里程碑 6（可选）：进阶功能
- [ ] 开机自启（把 exe 快捷方式放进启动文件夹）
- [ ] 托盘图标（最小化到系统托盘）
- [ ] 多显示器边界适配
- [ ] 声音反馈（被撸时喵一声）
