# 给设计师朋友的极简指南

不需要懂 Git，不需要命令行（除了一次依赖安装）。全程图形界面。

下面 4 件事覆盖所有日常使用：**装一次** → **用** → **改完分享** → **拿最新版**。

---

## 1. 一次性安装（约 10 分钟）

### 1.1 装 GitHub Desktop

下载：<https://desktop.github.com>

安装完打开，用你的 GitHub 账号登录。如果没有账号，去 github.com 免费注册一个。

### 1.2 把 skill 拉到你的电脑

1. 浏览器打开：<https://github.com/ideryang/pdf-to-pptx-clone>
2. 点页面右上角绿色的 **`< > Code`** 按钮 → 选 **Open with GitHub Desktop**
3. GitHub Desktop 弹窗里有一项 **"Local path"**——一定改成下面这个路径（把 `<你的用户名>` 换成你 Mac 的用户名）：

   ```
   /Users/<你的用户名>/.claude/skills/pdf-to-pptx-clone
   ```

   > 不知道你的用户名？打开"终端"输 `whoami` 回车，显示的就是。

4. 点 **Clone** 按钮，等它下载完

### 1.3 装 Python 依赖（只有这一步要开终端）

打开 **终端**（Spotlight 搜 "Terminal"），粘贴下面这行，回车：

```bash
pip3 install --user PyMuPDF python-pptx Pillow fonttools
```

等它跑完（看到 `Successfully installed ...` 就行），关掉终端。

**完事。skill 装好了，以后就不用再碰终端了。**

---

## 2. 怎么用

打开 Claude Code，新开一个会话，**直接说人话**：

- *"帮我把这个 PDF 转成 PPT"* + 把 PDF 拖进来
- *"用这份 PDF 的设计风格做一份新的 deck"*
- *"克隆这个 PDF 成 PowerPoint"*

Claude 会自动：

1. 问你选 **Clone 模式**（像素级还原原 PDF，保留所有文字和图）还是 **Sibling 模式**（继承设计语言，写全新英文内容）
2. 如果你选 Sibling，再问你 topic——给你 22 个预设主题（品牌营销 / 创业融资 / 产品发布 / 摄影旅行 / ...）或者你自己描述一个
3. 自动跑完整条 pipeline，最后给你一个 `.pptx` 文件

你只需要选选答答，全程不用敲命令。

---

## 3. 你改了点东西、想分享给大家

设计师友好的工作流是这样：**让 Claude 改代码 → GitHub Desktop 提交 → 浏览器开 PR**。

### 3.1 让 Claude 帮你改

在 Claude Code 里说人话就行，比如：

- *"sibling deck 第 7 页字体太小了，调大一点"*
- *"我希望 Pexels 抓图时偏好横版构图"*
- *"加一种新的 topic 选项：'食品包装设计'"*

Claude 会直接改 skill 里对应的文件。改完它会告诉你改了哪些。

### 3.2 用 GitHub Desktop 提交

1. 打开 GitHub Desktop——你会看到**左栏列出所有改过的文件**
2. **顶部 "Current Branch"** 下拉 → 点 **"New branch"** → 起个能看懂的名字（中文也行）：
   - 比如 `修复-封面-字体` 或 `add-packaging-topic`
3. **左下角**写一句话说明你做了什么（中文也行）
   - 比如："修了 sibling cover 字体在 macOS 上 fallback 的问题"
4. 点 **"Commit to <你的分支名>"** 按钮
5. 顶部 **"Publish branch"** 按钮亮起 → 点一下

### 3.3 开 PR 让别人 review（浏览器里完成）

刚 publish 完，GitHub Desktop 上方会出现一个蓝色按钮 **"Create Pull Request"** → 点击 → 自动跳到浏览器。

在浏览器里：

1. 标题写清你改了什么（GitHub Desktop 自动填了你的 commit message，一般不用改）
2. 描述里可以加张截图（拖图片到输入框就行）说明效果
3. 右侧 **Reviewers** 选另一个人
4. 点最下面绿色 **"Create pull request"**

**完事**。等另一个人 review、批准、合并就好。合并后他/她和其他人 `git pull` 都会拿到你的改动。

> **特别小事**（修个错别字、改个数字）懒得开 PR？可以在 GitHub Desktop 的 Current Branch 选 main，直接 Commit + Push。不推荐，但小到不会出事的话可以。

---

## 4. 拿别人的最新更新

打开 **GitHub Desktop** → 顶部 **"Fetch origin"** 按钮 → 如果提示变成 **"Pull origin"** 就点它。

完事。下次在 Claude Code 用 skill，自动是新版。

---

## 常见问题

**Q: 我开了 PR，但是上面有个红色的 ✗ 是什么？**

A: 那是自动校验（CI）。点开看哪一步红了——多半是 SKILL.md 格式或脚本有语法错。让 Claude 看一眼修一下，再 commit + push 到同一个分支，CI 会自动重跑。

**Q: GitHub Desktop 说 "There are uncommitted changes" 不让我切分支怎么办？**

A: 你有没保存的改动。要么先在 GitHub Desktop 提交（左下角写消息 + Commit），要么 **Discard Changes** 扔掉。

**Q: Claude 改的文件我能预览吗？**

A: 在 GitHub Desktop 左栏点任意一个文件名，右侧会显示**红绿对比**——红色是被删掉的旧版本，绿色是新版本。

**Q: 我把仓库克隆错地方了怎么办？**

A: 在 GitHub Desktop 里 File → Remove repository（不会删本地文件，只是从列表移除）。然后回到上面 **1.2** 重新做一遍，路径改对。

**Q: skill 没生效？**

A: 三个最常见原因：
1. 路径不对——克隆的目录必须是 `/Users/<你>/.claude/skills/pdf-to-pptx-clone`，不是别的
2. 依赖没装——回到 **1.3** 跑那行 pip
3. Claude Code 没重启——彻底退出再开

---

需要帮忙了直接在 [GitHub Issues](https://github.com/ideryang/pdf-to-pptx-clone/issues/new/choose) 开一个，会有现成的模板让你填。
