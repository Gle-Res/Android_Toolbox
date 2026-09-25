# -*- coding: utf-8 -*-
"""
安卓工具箱 (Android Toolbox)
依赖：PyQt5
"""

import sys
import os
import re
import time
import subprocess
import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QLabel, QLineEdit, QPushButton,
    QTextEdit, QFileDialog, QComboBox, QMessageBox, QStackedWidget,
    QFormLayout, QSplitter, QInputDialog, QGridLayout, QFrame,
    QScrollArea, QStatusBar, QCheckBox, QGroupBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QProcess
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter, QColor, QBrush

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


# ==================== 工具路径查找 ====================
def app_base_dir():
    """程序所在目录（兼容打包成 exe）"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def find_adb():
    """自动查找 adb.exe：优先程序同级 → 环境变量 → 常见路径"""
    base = app_base_dir()
    for c in [
        os.path.join(base, "platform-tools", "adb.exe"),
        os.path.join(base, "adb.exe"),
        os.path.join(base, "scrcpy", "adb.exe"),
    ]:
        if os.path.isfile(c):
            return c

    try:
        subprocess.run(["adb", "version"], capture_output=True, check=True,
                       shell=True, creationflags=CREATE_NO_WINDOW)
        return "adb"
    except Exception:
        pass

    for c in [
        r"D:\Program Files\ADB Wireless Tool\platform-tools\adb.exe",
        r"C:\platform-tools\adb.exe",
        r"C:\adb\adb.exe",
        os.path.expanduser(r"~\platform-tools\adb.exe"),
        os.path.expanduser(r"~\AppData\Local\Android\Sdk\platform-tools\adb.exe"),
    ]:
        if os.path.isfile(c):
            return c
    return "adb"


def find_scrcpy():
    """自动查找 scrcpy.exe：优先程序同级 → 环境变量 → 常见路径"""
    base = app_base_dir()
    for c in [
        os.path.join(base, "scrcpy", "scrcpy.exe"),
        os.path.join(base, "scrcpy.exe"),
        os.path.join(base, "scrcpy", "scrcpy-noconsole.exe"),
        os.path.join(base, "platform-tools", "scrcpy.exe"),
    ]:
        if os.path.isfile(c):
            return c

    try:
        subprocess.run(["scrcpy", "--version"], capture_output=True,
                       check=True, shell=True, creationflags=CREATE_NO_WINDOW)
        return "scrcpy"
    except Exception:
        pass

    for c in [
        r"D:\Program Files\scrcpy\scrcpy.exe",
        r"D:\scrcpy\scrcpy.exe",
        r"C:\scrcpy\scrcpy.exe",
        os.path.expanduser(r"~\scrcpy\scrcpy.exe"),
        os.path.expanduser(r"~\Downloads\scrcpy\scrcpy.exe"),
    ]:
        if os.path.isfile(c):
            return c
    return ""


ADB = find_adb()


def run_cmd(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           shell=isinstance(cmd, str),
                           encoding="utf-8", errors="replace",
                           creationflags=CREATE_NO_WINDOW)
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode == 0, out.strip()
    except subprocess.TimeoutExpired:
        return False, "❌ 命令执行超时"
    except Exception as e:
        return False, f"❌ 执行出错：{e}"


def kill_process_by_name(name):
    """杀掉指定名字的进程（Windows taskkill）"""
    try:
        r = subprocess.run(["taskkill", "/F", "/IM", name],
                           capture_output=True, text=True,
                           encoding="gbk", errors="replace",
                           creationflags=CREATE_NO_WINDOW)
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode == 0, out.strip()
    except Exception as e:
        return False, str(e)


BATTERY_HEALTH = {
    "1": "❔ 未知", "2": "✅ 良好", "3": "⚠️ 过热", "4": "❌ 已损坏",
    "5": "⚠️ 过压", "6": "❌ 未指定故障", "7": "⚠️ 过冷",
}
BATTERY_STATUS = {
    "1": "❔ 未知", "2": "⚡ 正在充电（充电器）", "3": "🔌 未充电",
    "4": "🔋 已充满", "5": "⚡ 正在充电（USB）",
    "6": "⚠️ 已断开", "7": "⚠️ 故障", "8": "⚠️ 已移除",
}


class CmdWorker(QThread):
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, cmd, timeout=60):
        super().__init__()
        self.cmd = cmd
        self.timeout = timeout

    def run(self):
        ok, out = run_cmd(self.cmd, self.timeout)
        self.finished_signal.emit(ok, out)


class InfoWorker(QThread):
    finished_signal = pyqtSignal(dict)

    def __init__(self, adb_prefix):
        super().__init__()
        self.pre = adb_prefix

    def sh(self, shell_cmd, timeout=15):
        ok, out = run_cmd(self.pre + ["shell"] + shell_cmd.split(), timeout)
        return out if ok else ""

    def run(self):
        info = {}
        try:
            info["品牌"] = self.sh("getprop ro.product.brand")
            info["型号"] = self.sh("getprop ro.product.model")
            info["设备代号"] = self.sh("getprop ro.product.device")
            info["序列号"] = self.sh("getprop ro.serialno")
            info["安卓版本"] = "Android " + self.sh("getprop ro.build.version.release")
            info["系统版本"] = self.sh("getprop ro.build.display.id")
            info["安全补丁"] = self.sh("getprop ro.build.version.security_patch")
            info["CPU架构"] = self.sh("getprop ro.product.cpu.abi")

            size = self.sh("wm size").replace("Physical size:", "").strip()
            density = self.sh("wm density").replace("Physical density:", "").strip()
            if size:
                info["屏幕分辨率"] = size
            if density:
                info["屏幕密度 DPI"] = density + " dpi"

            battery = self.sh("dumpsys battery")
            for line in battery.splitlines():
                line = line.strip()
                if line.startswith("level:"):
                    info["电池电量"] = line.split(":", 1)[1].strip() + "%"
                elif line.startswith("health:"):
                    h = line.split(":", 1)[1].strip()
                    info["电池健康"] = BATTERY_HEALTH.get(h, h)
                elif line.startswith("status:"):
                    s = line.split(":", 1)[1].strip()
                    info["充电状态"] = BATTERY_STATUS.get(s, s)
                elif line.startswith("temperature:"):
                    t = line.split(":", 1)[1].strip()
                    try:
                        info["电池温度"] = f"{int(t)/10:.1f} ℃"
                    except:
                        info["电池温度"] = t
                elif line.startswith("voltage:"):
                    v = line.split(":", 1)[1].strip()
                    try:
                        info["电池电压"] = f"{int(v)/1000:.2f} V"
                    except:
                        info["电池电压"] = v
                elif line.startswith("technology:"):
                    info["电池类型"] = line.split(":", 1)[1].strip()

            mem = self.sh("cat /proc/meminfo")
            total_kb = avail_kb = None
            for line in mem.splitlines():
                if line.startswith("MemTotal:"):
                    total_kb = int(re.findall(r"\d+", line)[0])
                elif line.startswith("MemAvailable:"):
                    avail_kb = int(re.findall(r"\d+", line)[0])
            if total_kb and avail_kb:
                total_gb = total_kb / 1024 / 1024
                used_gb = (total_kb - avail_kb) / 1024 / 1024
                pct = used_gb / total_gb * 100
                info["运行内存"] = f"{used_gb:.2f} GB / {total_gb:.2f} GB（占用 {pct:.0f}%）"

            df = self.sh("df /data")
            for line in df.splitlines():
                if "/data" in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        try:
                            total = int(parts[1]) / 1024 / 1024
                            used = int(parts[2]) / 1024 / 1024
                            pct = used / total * 100
                            info["存储空间"] = f"{used:.2f} GB / {total:.2f} GB（占用 {pct:.0f}%）"
                        except:
                            pass

            cpu = self.sh("cat /proc/cpuinfo")
            hw = re.findall(r"Hardware\s*:\s*(.+)", cpu)
            if hw:
                info["CPU型号"] = hw[0].strip()
            cores = cpu.count("processor")
            if cores:
                info["CPU核心数"] = f"{cores} 核"

            uptime = self.sh("cat /proc/uptime")
            if uptime:
                sec = float(uptime.split()[0])
                d = int(sec // 86400)
                h = int((sec % 86400) // 3600)
                m = int((sec % 3600) // 60)
                info["开机时长"] = f"{d} 天 {h} 小时 {m} 分钟" if d else f"{h} 小时 {m} 分钟"
        except Exception as e:
            info["读取失败"] = str(e)
        self.finished_signal.emit(info)


def make_app_icon():
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QBrush(QColor("#3DDC84")))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(2, 2, 60, 60, 14, 14)
    p.setBrush(QBrush(QColor("#FFFFFF")))
    p.drawRoundedRect(18, 22, 28, 22, 8, 8)
    p.setBrush(QBrush(QColor("#0F172A")))
    p.drawEllipse(25, 29, 4, 4)
    p.drawEllipse(35, 29, 4, 4)
    p.setPen(QColor("#FFFFFF"))
    p.drawLine(24, 22, 21, 16)
    p.drawLine(40, 22, 43, 16)
    p.end()
    return QIcon(pix)


class AdbTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("安卓工具箱")
        self.setWindowIcon(make_app_icon())
        self.resize(1280, 800)
        self.setMinimumSize(1100, 680)

        self.devices = []
        self.current_serial = None
        self.scrcpy_process = None
        self.workers = []          # ★ 线程池，防止被 GC

        self.init_ui()
        self.setStyleSheet(self.load_qss())
        self.refresh_devices()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ========== 左侧 ==========
        left_widget = QWidget()
        left_widget.setObjectName("LeftPanel")
        left_widget.setFixedWidth(240)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        logo_wrap = QWidget()
        logo_wrap.setObjectName("LogoWrap")
        logo_wrap.setFixedHeight(84)
        logo_layout = QHBoxLayout(logo_wrap)
        logo_layout.setContentsMargins(20, 0, 12, 0)
        logo_layout.setSpacing(12)
        logo_icon = QLabel()
        logo_icon.setPixmap(make_app_icon().pixmap(40, 40))
        logo_icon.setFixedSize(40, 40)
        logo_text = QLabel("安卓工具箱")
        logo_text.setObjectName("LogoText")
        logo_layout.addWidget(logo_icon)
        logo_layout.addWidget(logo_text)
        logo_layout.addStretch(1)
        left_layout.addWidget(logo_wrap)

        self.func_list = QListWidget()
        self.func_list.setObjectName("FuncList")
        self.func_list.setFont(QFont("Microsoft YaHei", 10))
        self.func_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.menu_items = [
            ("group", "设备", None),
            ("item", "📱  设备信息", "device_info"),
            ("item", "🔌  设备管理", "device_manage"),
            ("group", "应用管理", None),
            ("item", "📦  安装 APK", "install_apk"),
            ("item", "🗑️  卸载应用", "uninstall"),
            ("item", "🧊  冻结 / 解冻", "freeze"),
            ("item", "🧹  清除数据", "clear_data"),
            ("item", "📋  应用列表", "app_list"),
            ("group", "文件传输", None),
            ("item", "📁  推送到手机", "push"),
            ("item", "📥  拉取到电脑", "pull"),
            ("item", "📸  屏幕截图", "screenshot"),
            ("item", "🎮  无线投屏控制", "scrcpy"),
            ("group", "系统工具", None),
            ("item", "🐚  ADB Shell", "shell"),
            ("item", "📜  查看日志", "logcat"),
            ("item", "🔁  重启设备", "reboot"),
            ("item", "⚙️  自定义命令", "custom"),
        ]

        self.func_list.blockSignals(True)
        self.first_item_row = None
        for i, (typ, label, key) in enumerate(self.menu_items):
            item = QListWidgetItem(label)
            if typ == "group":
                item.setFlags(Qt.NoItemFlags)
                item.setFont(QFont("Microsoft YaHei", 9, QFont.Bold))
                item.setForeground(QColor("#64748b"))
                item.setSizeHint(QSize(0, 32))
                item.setData(Qt.UserRole, "__GROUP__")
            else:
                item.setData(Qt.UserRole, key)
                item.setSizeHint(QSize(0, 44))
                if self.first_item_row is None:
                    self.first_item_row = i
            self.func_list.addItem(item)
        self.func_list.blockSignals(False)
        self.func_list.currentRowChanged.connect(self.on_func_changed)
        left_layout.addWidget(self.func_list, 1)

        ver = QLabel("v2.0.0  ·  Powered by ADB + scrcpy")
        ver.setObjectName("VersionLabel")
        ver.setAlignment(Qt.AlignCenter)
        ver.setFixedHeight(36)
        left_layout.addWidget(ver)

        # ========== 右侧 ==========
        right_widget = QWidget()
        right_widget.setObjectName("RightPanel")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        topbar = QWidget()
        topbar.setObjectName("TopBar")
        topbar.setFixedHeight(64)
        tb = QHBoxLayout(topbar)
        tb.setContentsMargins(24, 0, 20, 0)
        tb.setSpacing(12)
        self.page_title = QLabel("设备信息")
        self.page_title.setObjectName("PageTitle")
        tb.addWidget(self.page_title)
        tb.addStretch(1)

        dev_label = QLabel("目标设备")
        dev_label.setObjectName("TopBarLabel")
        self.device_combo = QComboBox()
        self.device_combo.setObjectName("DeviceCombo")
        self.device_combo.setMinimumWidth(300)
        btn_refresh = QPushButton("刷新")
        btn_refresh.setObjectName("BtnRefresh")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.clicked.connect(self.refresh_devices)
        tb.addWidget(dev_label)
        tb.addWidget(self.device_combo)
        tb.addWidget(btn_refresh)
        right_layout.addWidget(topbar)

        content_wrap = QWidget()
        content_wrap.setObjectName("ContentWrap")
        content_layout = QVBoxLayout(content_wrap)
        content_layout.setContentsMargins(24, 18, 24, 18)
        content_layout.setSpacing(14)
        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack, 1)
        right_layout.addWidget(content_wrap, 1)

        self.page_widgets = {}
        self.build_pages()

        main_layout.addWidget(left_widget)
        main_layout.addWidget(right_widget, 1)

        self.status = QStatusBar()
        self.status.setObjectName("AppStatusBar")
        self.setStatusBar(self.status)
        self.status.showMessage("就绪")

        if self.first_item_row is not None:
            self.func_list.setCurrentRow(self.first_item_row)

    def build_pages(self):
        # ===== 设备信息 =====
        page = QWidget()
        pl = QVBoxLayout(page)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(12)

        banner = QFrame()
        banner.setObjectName("Banner")
        bl = QHBoxLayout(banner)
        bl.setContentsMargins(20, 14, 20, 14)
        bl.setSpacing(14)
        bi = QLabel("🔍")
        bi.setStyleSheet("font-size: 24px;")
        btw = QVBoxLayout()
        btw.setSpacing(2)
        self.banner_title = QLabel("读取当前设备的全部信息")
        self.banner_title.setObjectName("BannerTitle")
        self.banner_sub = QLabel("包括型号、系统、硬件、电池、运行状态等中文描述")
        self.banner_sub.setObjectName("BannerSub")
        btw.addWidget(self.banner_title)
        btw.addWidget(self.banner_sub)
        self.btn_load_info = QPushButton("开始读取")
        self.btn_load_info.setObjectName("PrimaryBtn")
        self.btn_load_info.setCursor(Qt.PointingHandCursor)
        self.btn_load_info.setMinimumWidth(120)
        self.btn_load_info.clicked.connect(self.load_device_info)
        bl.addWidget(bi)
        bl.addLayout(btw, 1)
        bl.addWidget(self.btn_load_info)
        pl.addWidget(banner)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setObjectName("InfoScroll")
        self.info_container = QWidget()
        self.info_container.setObjectName("InfoContainer")
        self.info_grid = QGridLayout(self.info_container)
        self.info_grid.setSpacing(14)
        self.info_grid.setContentsMargins(0, 6, 0, 6)
        scroll.setWidget(self.info_container)
        pl.addWidget(scroll, 1)

        self.add_page("device_info", page)

        # ===== 设备管理 =====
        page, v = self.make_plain_page()
        v.addWidget(self.section_title("设备管理操作"))
        for name, cb in [
            ("🔍 列出所有已连接设备", self.cmd_list_devices),
            ("🔌 无线连接设备（输入 IP:端口）", self.cmd_connect_wireless),
            ("❌ 断开所有无线设备（结束 adb.exe 进程）", self.cmd_disconnect_all),
            ("🔄 重启 ADB 服务", self.cmd_restart_adb),
        ]:
            b = QPushButton(name)
            b.setObjectName("NormalBtn")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(cb)
            v.addWidget(b)
        v.addWidget(self.make_output_box(), 1)
        self.add_page("device_manage", page)

        # ===== 安装 APK =====
        page, form = self.make_form_page()
        form.addRow(self.section_title("安装 APK"))
        self.apk_path = QLineEdit()
        self.apk_path.setPlaceholderText("选择 APK 文件...")
        bb = QPushButton("浏览")
        bb.setCursor(Qt.PointingHandCursor)
        bb.clicked.connect(self.browse_apk)
        row = QHBoxLayout()
        row.addWidget(self.apk_path, 1)
        row.addWidget(bb)
        form.addRow("APK 路径：", self.wrap_layout(row))
        self.apk_opt = QComboBox()
        self.apk_opt.addItems(["普通安装", "覆盖安装 -r", "降级安装 -d", "覆盖+降级 -r -d"])
        form.addRow("安装方式：", self.apk_opt)
        b = QPushButton("📦 开始安装")
        b.setObjectName("PrimaryBtn")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(self.cmd_install_apk)
        form.addRow(b)
        form.addRow(self.make_output_box())
        self.add_page("install_apk", page)

        # ===== 卸载应用 =====
        page, form = self.make_form_page()
        form.addRow(self.section_title("卸载应用"))
        self.uninstall_pkg = QLineEdit()
        self.uninstall_pkg.setPlaceholderText("例如：com.miui.video")
        form.addRow("包名：", self.uninstall_pkg)
        self.uninstall_keep = QComboBox()
        self.uninstall_keep.addItems(["不保留数据", "保留数据 -k"])
        form.addRow("选项：", self.uninstall_keep)
        b = QPushButton("🗑️ 卸载")
        b.setObjectName("DangerBtn")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(self.cmd_uninstall)
        form.addRow(b)
        form.addRow(self.make_output_box())
        self.add_page("uninstall", page)

        # ===== 冻结 / 解冻 =====
        page, form = self.make_form_page()
        form.addRow(self.section_title("冻结 / 解冻应用"))
        self.freeze_pkg = QLineEdit()
        self.freeze_pkg.setPlaceholderText("例如：com.miui.video")
        form.addRow("包名：", self.freeze_pkg)
        b = QPushButton("🧊 冻结（禁用）")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda: self.cmd_freeze(True))
        form.addRow(b)
        b2 = QPushButton("☀️ 解冻（启用）")
        b2.setCursor(Qt.PointingHandCursor)
        b2.clicked.connect(lambda: self.cmd_freeze(False))
        form.addRow(b2)
        form.addRow(self.make_output_box())
        self.add_page("freeze", page)

        # ===== 清除数据 =====
        page, form = self.make_form_page()
        form.addRow(self.section_title("清除应用数据"))
        self.clear_pkg = QLineEdit()
        self.clear_pkg.setPlaceholderText("例如：com.miui.video")
        form.addRow("包名：", self.clear_pkg)
        b = QPushButton("🧹 清除应用数据")
        b.setObjectName("DangerBtn")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(self.cmd_clear_data)
        form.addRow(b)
        form.addRow(self.make_output_box())
        self.add_page("clear_data", page)

        # ===== 应用列表 =====
        page, form = self.make_form_page()
        form.addRow(self.section_title("列出应用"))
        self.list_type = QComboBox()
        self.list_type.addItems(["全部应用", "仅第三方 -3", "仅系统 -s"])
        form.addRow("类型：", self.list_type)
        b = QPushButton("📋 列出应用")
        b.setObjectName("PrimaryBtn")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(self.cmd_list_packages)
        form.addRow(b)
        form.addRow(self.make_output_box())
        self.add_page("app_list", page)

        # ===== push =====
        page, form = self.make_form_page()
        form.addRow(self.section_title("文件推送到手机"))
        self.push_local = QLineEdit()
        self.push_local.setPlaceholderText("本地文件路径")
        b1 = QPushButton("浏览")
        b1.setCursor(Qt.PointingHandCursor)
        b1.clicked.connect(self.browse_push_file)
        row = QHBoxLayout()
        row.addWidget(self.push_local, 1)
        row.addWidget(b1)
        form.addRow("本地文件：", self.wrap_layout(row))
        self.push_remote = QLineEdit("/sdcard/")
        form.addRow("手机目标路径：", self.push_remote)
        b = QPushButton("📁 推送到手机")
        b.setObjectName("PrimaryBtn")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(self.cmd_push)
        form.addRow(b)
        form.addRow(self.make_output_box())
        self.add_page("push", page)

        # ===== pull =====
        page, form = self.make_form_page()
        form.addRow(self.section_title("文件拉取到电脑"))
        self.pull_remote = QLineEdit()
        self.pull_remote.setPlaceholderText("手机文件路径，如 /sdcard/a.jpg")
        form.addRow("手机文件：", self.pull_remote)
        self.pull_local = QLineEdit()
        self.pull_local.setPlaceholderText("电脑保存目录")
        b1 = QPushButton("浏览")
        b1.setCursor(Qt.PointingHandCursor)
        b1.clicked.connect(self.browse_pull_dir)
        row = QHBoxLayout()
        row.addWidget(self.pull_local, 1)
        row.addWidget(b1)
        form.addRow("电脑目录：", self.wrap_layout(row))
        b = QPushButton("📥 拉取到电脑")
        b.setObjectName("PrimaryBtn")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(self.cmd_pull)
        form.addRow(b)
        form.addRow(self.make_output_box())
        self.add_page("pull", page)

        # ===== 截屏 =====
        page, form = self.make_form_page()
        form.addRow(self.section_title("屏幕截图"))
        self.screenshot_dir = QLineEdit(os.path.expanduser("~/Desktop"))
        b1 = QPushButton("浏览")
        b1.setCursor(Qt.PointingHandCursor)
        b1.clicked.connect(self.browse_screenshot_dir)
        row = QHBoxLayout()
        row.addWidget(self.screenshot_dir, 1)
        row.addWidget(b1)
        form.addRow("保存目录：", self.wrap_layout(row))
        b = QPushButton("📸 截屏并保存到电脑")
        b.setObjectName("PrimaryBtn")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(self.cmd_screenshot)
        form.addRow(b)
        form.addRow(self.make_output_box())
        self.add_page("screenshot", page)

        # ===== 无线投屏控制 (scrcpy) =====
        page, v = self.make_plain_page()
        v.addWidget(self.section_title("无线投屏控制 · scrcpy"))

        path_row = QHBoxLayout()
        self.scrcpy_path = QLineEdit()
        self.scrcpy_path.setPlaceholderText("选择 scrcpy.exe 路径（已在 PATH 可留空）")
        self.scrcpy_path.setText(find_scrcpy())
        btn_pick = QPushButton("浏览")
        btn_pick.setCursor(Qt.PointingHandCursor)
        btn_pick.clicked.connect(self.browse_scrcpy)
        path_row.addWidget(self.scrcpy_path, 1)
        path_row.addWidget(btn_pick)
        v.addWidget(self.wrap_layout(path_row))

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("连接模式："))
        self.scrcpy_mode = QComboBox()
        self.scrcpy_mode.addItems([
            "USB 直连（当前已连接设备）",
            "无线（自动 tcpip 5555 + 连接）",
        ])
        mode_row.addWidget(self.scrcpy_mode, 1)
        v.addLayout(mode_row)

        ip_row = QHBoxLayout()
        ip_row.addWidget(QLabel("设备 IP："))
        self.scrcpy_ip = QLineEdit()
        self.scrcpy_ip.setPlaceholderText("留空则自动从 adb 获取，例如 192.168.0.110")
        ip_row.addWidget(self.scrcpy_ip, 1)
        v.addLayout(ip_row)

        opt_box = QGroupBox("投屏参数")
        opt_box.setObjectName("OptBox")
        opt_grid = QGridLayout(opt_box)
        opt_grid.setSpacing(10)

        self.opt_maxsize = QCheckBox("限制最大分辨率")
        self.val_maxsize = QLineEdit("1024")
        self.val_maxsize.setFixedWidth(90)

        self.opt_bitrate = QCheckBox("限制码率 (Mbps)")
        self.val_bitrate = QLineEdit("8")
        self.val_bitrate.setFixedWidth(90)

        self.opt_noaudio = QCheckBox("关闭音频")
        self.opt_noaudio.setChecked(True)

        self.opt_stayawake = QCheckBox("保持屏幕常亮")
        self.opt_stayawake.setChecked(True)

        self.opt_borderless = QCheckBox("无窗口边框")
        self.opt_fullscreen = QCheckBox("全屏启动")

        self.opt_record = QCheckBox("录制到 MP4")
        self.val_record = QLineEdit(os.path.expanduser("~/Desktop/record.mp4"))
        btn_rec = QPushButton("...")
        btn_rec.setFixedWidth(36)
        btn_rec.setCursor(Qt.PointingHandCursor)
        btn_rec.clicked.connect(self.browse_record_path)
        rec_row = QHBoxLayout()
        rec_row.addWidget(self.val_record, 1)
        rec_row.addWidget(btn_rec)

        opt_grid.addWidget(self.opt_maxsize, 0, 0)
        opt_grid.addWidget(self.val_maxsize, 0, 1)
        opt_grid.addWidget(self.opt_bitrate, 0, 2)
        opt_grid.addWidget(self.val_bitrate, 0, 3)
        opt_grid.addWidget(self.opt_noaudio, 0, 4)
        opt_grid.addWidget(self.opt_stayawake, 0, 5)
        opt_grid.addWidget(self.opt_borderless, 1, 0)
        opt_grid.addWidget(self.opt_fullscreen, 1, 1)
        opt_grid.addWidget(self.opt_record, 1, 2)
        opt_grid.addLayout(rec_row, 1, 3, 1, 3)
        v.addWidget(opt_box)

        btn_row = QHBoxLayout()
        self.btn_launch_scrcpy = QPushButton("🎮 启动投屏")
        self.btn_launch_scrcpy.setObjectName("PrimaryBtn")
        self.btn_launch_scrcpy.setCursor(Qt.PointingHandCursor)
        self.btn_launch_scrcpy.clicked.connect(self.launch_scrcpy)

        self.btn_stop_scrcpy = QPushButton("🛑 停止投屏")
        self.btn_stop_scrcpy.setObjectName("DangerBtn")
        self.btn_stop_scrcpy.setCursor(Qt.PointingHandCursor)
        self.btn_stop_scrcpy.setEnabled(False)
        self.btn_stop_scrcpy.clicked.connect(self.stop_scrcpy)

        btn_row.addWidget(self.btn_launch_scrcpy)
        btn_row.addWidget(self.btn_stop_scrcpy)
        btn_row.addStretch(1)
        v.addLayout(btn_row)

        v.addWidget(self.make_output_box(), 1)
        self.add_page("scrcpy", page)

        # ===== Shell =====
        page, v = self.make_plain_page()
        v.addWidget(self.section_title("ADB Shell"))
        tip = QLabel("输入 shell 命令（不带 adb shell 前缀）")
        tip.setObjectName("HintLabel")
        v.addWidget(tip)
        self.shell_input = QLineEdit()
        self.shell_input.setPlaceholderText("例如：getprop ro.product.model")
        self.shell_input.setFont(QFont("Consolas", 10))
        self.shell_input.returnPressed.connect(self.cmd_shell)
        v.addWidget(self.shell_input)
        b = QPushButton("🐚 执行 Shell 命令")
        b.setObjectName("PrimaryBtn")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(self.cmd_shell)
        v.addWidget(b)
        v.addWidget(self.make_output_box(), 1)
        self.add_page("shell", page)

        # ===== Logcat =====
        page, form = self.make_form_page()
        form.addRow(self.section_title("查看日志 Logcat"))
        self.log_filter = QLineEdit()
        self.log_filter.setPlaceholderText("过滤 TAG，可留空")
        form.addRow("TAG 过滤：", self.log_filter)
        self.log_mode = QComboBox()
        self.log_mode.addItems(["一次性日志 -d", "只抓崩溃日志", "清空日志缓存"])
        form.addRow("模式：", self.log_mode)
        b = QPushButton("📜 执行")
        b.setObjectName("PrimaryBtn")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(self.cmd_logcat)
        form.addRow(b)
        form.addRow(self.make_output_box())
        self.add_page("logcat", page)

        # ===== 重启 =====
        page, v = self.make_plain_page()
        v.addWidget(self.section_title("重启设备"))
        for name, arg in [
            ("🔁 普通重启", "reboot"),
            ("🛠️ 重启到 Recovery", "reboot recovery"),
            ("⚡ 重启到 Fastboot", "reboot bootloader"),
        ]:
            b = QPushButton(name)
            b.setObjectName("DangerBtn")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _, a=arg: self.cmd_reboot(a))
            v.addWidget(b)
        v.addWidget(self.make_output_box(), 1)
        self.add_page("reboot", page)

        # ===== 自定义 =====
        page, v = self.make_plain_page()
        v.addWidget(self.section_title("自定义 ADB 命令"))
        tip = QLabel("输入任意 ADB 命令（无需写 adb 前缀）")
        tip.setObjectName("HintLabel")
        v.addWidget(tip)
        self.custom_cmd = QLineEdit()
        self.custom_cmd.setPlaceholderText("例如：devices 或 shell input keyevent 3")
        self.custom_cmd.setFont(QFont("Consolas", 10))
        self.custom_cmd.returnPressed.connect(self.cmd_custom)
        v.addWidget(self.custom_cmd)
        b = QPushButton("⚙️ 执行")
        b.setObjectName("PrimaryBtn")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(self.cmd_custom)
        v.addWidget(b)
        v.addWidget(self.make_output_box(), 1)
        self.add_page("custom", page)

    def add_page(self, key, page):
        self.stack.addWidget(page)
        self.page_widgets[key] = page

    def make_form_page(self):
        page = QWidget()
        form = QFormLayout(page)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignTop)
        form.setSpacing(12)
        form.setContentsMargins(0, 0, 0, 0)
        return page, form

    def make_plain_page(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)
        return page, v

    def section_title(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("SectionTitle")
        return lbl

    def wrap_layout(self, layout):
        w = QWidget()
        w.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)
        return w

    def make_output_box(self):
        box = QTextEdit()
        box.setObjectName("OutputArea")
        box.setReadOnly(True)
        box.setFont(QFont("Consolas", 10))
        box.setPlaceholderText("命令执行结果会显示在这里...")
        box.setMinimumHeight(160)
        return box

    def current_output(self):
        w = self.stack.currentWidget()
        if w:
            for child in w.findChildren(QTextEdit):
                if child.objectName() == "OutputArea":
                    return child
        return None

    def append_log(self, text):
        box = self.current_output()
        if box:
            box.append(text)
            box.verticalScrollBar().setValue(box.verticalScrollBar().maximum())

    def on_func_changed(self, idx):
        item = self.func_list.item(idx)
        if item is None:
            return
        key = item.data(Qt.UserRole)
        if key == "__GROUP__":
            self.func_list.setCurrentRow(idx + 1)
            return
        if key in self.page_widgets:
            self.stack.setCurrentWidget(self.page_widgets[key])
            title = item.text().strip()
            title = re.sub(r"^[^\u4e00-\u9fa5A-Za-z]+", "", title).strip()
            self.page_title.setText(title)

    # ---------- 设备 ----------
    def refresh_devices(self):
        ok, out = run_cmd([ADB, "devices"])
        self.devices = []
        if ok:
            for line in out.splitlines()[1:]:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    self.devices.append((parts[0], parts[1]))
        self.device_combo.clear()
        if not self.devices:
            self.device_combo.addItem("（未检测到设备）")
            self.current_serial = None
            self.status.showMessage("❌ 未检测到设备")
        else:
            for serial, state in self.devices:
                self.device_combo.addItem(f"{serial}   [{state}]", serial)
            self.current_serial = self.devices[0][0]
            self.status.showMessage(f"✅ 已连接 {len(self.devices)} 台设备")

    def get_serial(self):
        data = self.device_combo.currentData()
        if not data:
            self.append_log("❌ 没有检测到设备，请连接后刷新。")
            return None
        return data

    def adb_prefix(self):
        s = self.get_serial()
        if not s:
            return None
        return [ADB, "-s", s]

    def run_async(self, cmd, timeout=60):
        """异步执行命令（线程池模式，防止 GC 崩溃）"""
        display = cmd if isinstance(cmd, str) else " ".join(cmd)
        self.append_log(f"$ {display}")
        worker = CmdWorker(cmd, timeout)
        self.workers.append(worker)
        worker.finished_signal.connect(self.on_cmd_finished)
        # 执行完成后自动从列表移除
        worker.finished_signal.connect(
            lambda *_, w=worker: self.workers.remove(w) if w in self.workers else None
        )
        worker.start()

    def on_cmd_finished(self, ok, out):
        prefix = "✅" if ok else "⚠️"
        self.append_log(f"{prefix} {out if out else '(无输出)'}\n")

    # ---------- 设备信息 ----------
    def load_device_info(self):
        pre = self.adb_prefix()
        if not pre:
            return
        self.btn_load_info.setEnabled(False)
        self.btn_load_info.setText("正在读取...")
        self.banner_title.setText("⏳ 正在读取设备信息，请稍候...")
        self.banner_sub.setText("大概需要 1~2 秒")
        while self.info_grid.count():
            item = self.info_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.info_worker = InfoWorker(pre)
        self.info_worker.finished_signal.connect(self.render_device_info)
        self.info_worker.start()

    def render_device_info(self, info):
        self.btn_load_info.setEnabled(True)
        self.btn_load_info.setText("重新读取")
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.banner_title.setText("✅ 设备信息读取完成")
        self.banner_sub.setText(f"最近更新于 {ts}   ·   已加载 {len(info)} 项信息")
        self.status.showMessage(f"设备信息读取完成（{ts}）")

        groups = [
            ("📱 设备基本信息", ["品牌", "型号", "设备代号", "序列号"]),
            ("🤖 系统信息", ["安卓版本", "系统版本", "安全补丁", "CPU架构",
                          "屏幕分辨率", "屏幕密度 DPI"]),
            ("⚙️ 硬件信息", ["CPU型号", "CPU核心数", "运行内存", "存储空间"]),
            ("🔋 电池信息", ["电池电量", "电池健康", "充电状态",
                          "电池温度", "电池电压", "电池类型"]),
            ("⏱️ 运行状态", ["开机时长"]),
        ]
        row = 0
        for title, keys in groups:
            t = QLabel(title)
            t.setObjectName("GroupTitle")
            self.info_grid.addWidget(t, row, 0, 1, 3)
            row += 1
            col = 0
            for key in keys:
                if key in info and info[key]:
                    card = self.make_info_card(key, info[key])
                    self.info_grid.addWidget(card, row, col)
                    col += 1
                    if col >= 3:
                        col = 0
                        row += 1
            if col != 0:
                row += 1
        self.info_grid.setRowStretch(row + 1, 1)

    def make_info_card(self, title, value):
        card = QFrame()
        card.setObjectName("InfoCard")
        card.setMinimumHeight(84)
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(4)
        lt = QLabel(title)
        lt.setObjectName("CardTitle")
        lv = QLabel(str(value))
        lv.setObjectName("CardValue")
        lv.setWordWrap(True)
        v.addWidget(lt)
        v.addWidget(lv)
        return card

    # ---------- 命令实现 ----------
    def cmd_list_devices(self):
        self.run_async([ADB, "devices"])

    def cmd_connect_wireless(self):
        """无线连接：串行执行，避免并发崩溃"""
        ip, ok = QInputDialog.getText(self, "无线连接", "输入 IP:端口（如 192.168.0.110:5555）：")
        if not ok or not ip.strip():
            return
        ip = ip.strip()
        self.append_log(f"📡 正在连接 {ip} ...")
        ok1, out1 = run_cmd([ADB, "connect", ip], timeout=15)
        self.append_log(f"$ adb connect {ip}\n{out1 if out1 else '(无输出)'}")
        if ok1 and "connected" in out1.lower():
            self.append_log("✅ 连接成功\n")
        else:
            self.append_log("⚠️ 连接失败，请检查 IP 和无线调试是否开启\n")
        self.refresh_devices()

    def cmd_disconnect_all(self):
        """断开所有无线设备 = 直接结束所有 adb.exe 进程"""
        reply = QMessageBox.question(
            self, "确认",
            "将强制结束所有 adb.exe 进程，断开全部 USB 和无线连接。\n确定继续？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.append_log("🛑 正在结束所有 adb.exe 进程...")
        ok, out = kill_process_by_name("adb.exe")
        if ok:
            self.append_log("✅ 已结束所有 adb.exe 进程")
        else:
            # taskkill 找不到进程时返回码非 0，这不算错误
            self.append_log(f"ℹ️ 结束结果：{out if out else '(未找到运行中的 adb.exe)'}")

        # 清理下设备列表显示
        time.sleep(0.5)
        self.append_log("💡 提示：需要重新连接设备时，点「🔍 列出所有已连接设备」会自动拉起 adb server\n")
        # 不调用 refresh_devices()，避免刚杀完又自动拉起
        self.device_combo.clear()
        self.device_combo.addItem("（adb 已停止）")
        self.current_serial = None
        self.status.showMessage("🛑 adb.exe 已结束")

    def cmd_restart_adb(self):
        """重启 ADB 服务：串行执行，避免并发崩溃"""
        reply = QMessageBox.question(
            self, "确认", "确定要重启 ADB 服务吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.append_log("🔄 正在重启 ADB 服务...")

        # 1. 先结束所有 adb.exe 进程
        ok0, out0 = kill_process_by_name("adb.exe")
        self.append_log(f"$ taskkill adb.exe\n{out0 if out0 else '(无运行中的 adb.exe)'}")
        time.sleep(1.0)

        # 2. 启动 server
        ok1, out1 = run_cmd([ADB, "start-server"], timeout=20)
        self.append_log(f"$ adb start-server\n{out1 if out1 else '(已启动)'}")
        time.sleep(1.0)

        # 3. 刷新设备
        self.refresh_devices()
        if self.devices:
            self.append_log(f"✅ ADB 服务已重启，检测到 {len(self.devices)} 台设备\n")
        else:
            self.append_log("✅ ADB 服务已重启（未检测到设备）\n")

    def browse_apk(self):
        p, _ = QFileDialog.getOpenFileName(self, "选择 APK", "", "APK 文件 (*.apk)")
        if p:
            self.apk_path.setText(p)

    def cmd_install_apk(self):
        p = self.apk_path.text().strip()
        if not p or not os.path.isfile(p):
            QMessageBox.warning(self, "提示", "请选择有效的 APK 文件")
            return
        pre = self.adb_prefix()
        if not pre:
            return
        opt = self.apk_opt.currentIndex()
        cmd = pre + ["install"]
        if opt == 1:
            cmd.append("-r")
        elif opt == 2:
            cmd.append("-d")
        elif opt == 3:
            cmd += ["-r", "-d"]
        cmd.append(p)
        self.run_async(cmd, timeout=180)

    def cmd_uninstall(self):
        pkg = self.uninstall_pkg.text().strip()
        if not pkg:
            QMessageBox.warning(self, "提示", "请输入包名")
            return
        pre = self.adb_prefix()
        if not pre:
            return
        cmd = pre + ["uninstall"]
        if self.uninstall_keep.currentIndex() == 1:
            cmd.append("-k")
        cmd.append(pkg)
        self.run_async(cmd, timeout=120)

    def cmd_freeze(self, freeze=True):
        pkg = self.freeze_pkg.text().strip()
        if not pkg:
            QMessageBox.warning(self, "提示", "请输入包名")
            return
        pre = self.adb_prefix()
        if not pre:
            return
        action = "disable-user" if freeze else "enable"
        self.run_async(pre + ["shell", "pm", action, pkg])

    def cmd_clear_data(self):
        pkg = self.clear_pkg.text().strip()
        if not pkg:
            QMessageBox.warning(self, "提示", "请输入包名")
            return
        pre = self.adb_prefix()
        if not pre:
            return
        self.run_async(pre + ["shell", "pm", "clear", pkg])

    def cmd_list_packages(self):
        pre = self.adb_prefix()
        if not pre:
            return
        cmd = pre + ["shell", "pm", "list", "packages"]
        idx = self.list_type.currentIndex()
        if idx == 1:
            cmd.append("-3")
        elif idx == 2:
            cmd.append("-s")
        self.run_async(cmd)

    def browse_push_file(self):
        p, _ = QFileDialog.getOpenFileName(self, "选择文件")
        if p:
            self.push_local.setText(p)

    def cmd_push(self):
        local = self.push_local.text().strip()
        remote = self.push_remote.text().strip() or "/sdcard/"
        if not local or not os.path.isfile(local):
            QMessageBox.warning(self, "提示", "请选择有效的本地文件")
            return
        pre = self.adb_prefix()
        if not pre:
            return
        self.run_async(pre + ["push", local, remote], timeout=300)

    def browse_pull_dir(self):
        p = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if p:
            self.pull_local.setText(p)

    def cmd_pull(self):
        remote = self.pull_remote.text().strip()
        local = self.pull_local.text().strip() or os.path.expanduser("~/Desktop")
        if not remote:
            QMessageBox.warning(self, "提示", "请输入手机文件路径")
            return
        pre = self.adb_prefix()
        if not pre:
            return
        self.run_async(pre + ["pull", remote, local], timeout=300)

    def cmd_shell(self):
        s = self.shell_input.text().strip()
        if not s:
            return
        pre = self.adb_prefix()
        if not pre:
            return
        self.run_async(pre + ["shell"] + s.split(), timeout=60)

    def cmd_logcat(self):
        pre = self.adb_prefix()
        if not pre:
            return
        idx = self.log_mode.currentIndex()
        if idx == 2:
            self.run_async(pre + ["logcat", "-c"])
            return
        cmd = pre + ["logcat", "-d"]
        if idx == 1:
            cmd += ["-b", "crash"]
        tag = self.log_filter.text().strip()
        if tag:
            cmd += ["-s", tag]
        self.run_async(cmd, timeout=30)

    def browse_screenshot_dir(self):
        p = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if p:
            self.screenshot_dir.setText(p)

    def cmd_screenshot(self):
        pre = self.adb_prefix()
        if not pre:
            return
        out_dir = self.screenshot_dir.text().strip() or os.path.expanduser("~/Desktop")
        if not os.path.isdir(out_dir):
            QMessageBox.warning(self, "提示", "保存目录不存在")
            return
        fname = "screenshot_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".png"
        out_path = os.path.join(out_dir, fname)
        remote = "/sdcard/_adb_screenshot_.png"
        self.append_log(f"$ adb shell screencap -p {remote}")
        ok, out = run_cmd(pre + ["shell", "screencap", "-p", remote])
        if not ok:
            self.append_log(f"⚠️ 截屏失败：{out}")
            return
        self.append_log(f"$ adb pull {remote} {out_path}")
        ok2, out2 = run_cmd(pre + ["pull", remote, out_path])
        if ok2:
            self.append_log(f"✅ 已保存：{out_path}")
        else:
            self.append_log(f"⚠️ 保存失败：{out2}")

    def cmd_reboot(self, arg):
        reply = QMessageBox.question(self, "确认", f"确定要执行 {arg} 吗？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        pre = self.adb_prefix()
        if not pre:
            return
        self.run_async(pre + [arg])

    def cmd_custom(self):
        s = self.custom_cmd.text().strip()
        if not s:
            return
        pre = self.adb_prefix()
        if not pre:
            return
        self.run_async(pre + s.split(), timeout=300)

    # ==================== scrcpy 无线投屏 ====================
    def browse_scrcpy(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "选择 scrcpy.exe", "", "可执行文件 (*.exe);;所有文件 (*)"
        )
        if p:
            self.scrcpy_path.setText(p)

    def browse_record_path(self):
        p, _ = QFileDialog.getSaveFileName(
            self, "保存录制文件", os.path.expanduser("~/Desktop/record.mp4"),
            "MP4 视频 (*.mp4)"
        )
        if p:
            self.val_record.setText(p)

    def get_device_ip(self, serial):
        ok, out = run_cmd([ADB, "-s", serial, "shell", "ip", "route"], timeout=10)
        if not ok:
            return None
        m = re.search(r"src\s+(\d+\.\d+\.\d+\.\d+)", out)
        if m:
            return m.group(1)
        return None

    def launch_scrcpy(self):
        scrcpy = self.scrcpy_path.text().strip() or find_scrcpy()
        if not scrcpy:
            QMessageBox.warning(self, "提示",
                "未找到 scrcpy.exe。\n\n"
                "请把 scrcpy 文件夹放到本程序同目录下（文件夹名必须是 scrcpy），\n"
                "或点击「浏览」手动选择 scrcpy.exe 路径。")
            return
        if scrcpy != "scrcpy" and not os.path.isfile(scrcpy):
            QMessageBox.warning(self, "提示", "scrcpy 路径无效，请重新选择")
            return

        serial = self.get_serial()
        if not serial:
            return

        mode = self.scrcpy_mode.currentIndex()
        target_serial = serial
        wireless_serial = None

        if mode == 1:
            self.append_log("📡 无线模式：正在切换设备到 TCP/IP 模式...")
            ok, out = run_cmd([ADB, "-s", serial, "tcpip", "5555"], timeout=15)
            self.append_log(f"$ adb -s {serial} tcpip 5555\n{out}")
            if not ok:
                self.append_log("⚠️ tcpip 切换失败，投屏终止")
                return

            time.sleep(2)

            ip = self.scrcpy_ip.text().strip()
            if not ip:
                ip = self.get_device_ip(serial)
                if not ip:
                    QMessageBox.warning(self, "提示",
                        "无法自动获取设备 IP，请在“设备 IP”里手动输入")
                    return
                self.scrcpy_ip.setText(ip)

            wireless_serial = f"{ip}:5555"
            ok2, out2 = run_cmd([ADB, "connect", wireless_serial], timeout=15)
            self.append_log(f"$ adb connect {wireless_serial}\n{out2}")
            if not ok2 or "connected" not in out2.lower():
                self.append_log("⚠️ 无线连接失败")
                return

            target_serial = wireless_serial
            self.append_log(f"✅ 无线连接成功：{wireless_serial}")

        cmd = [scrcpy, "-s", target_serial]

        if self.opt_maxsize.isChecked() and self.val_maxsize.text().strip():
            cmd += ["--max-size", self.val_maxsize.text().strip()]
        if self.opt_bitrate.isChecked() and self.val_bitrate.text().strip():
            cmd += ["--bit-rate", self.val_bitrate.text().strip() + "M"]
        if self.opt_noaudio.isChecked():
            cmd += ["--no-audio"]
        if self.opt_stayawake.isChecked():
            cmd += ["--stay-awake"]
        if self.opt_borderless.isChecked():
            cmd += ["--window-borderless"]
        if self.opt_fullscreen.isChecked():
            cmd += ["--fullscreen"]
        if self.opt_record.isChecked() and self.val_record.text().strip():
            cmd += ["--record", self.val_record.text().strip()]

        self.append_log(f"$ {' '.join(cmd)}")
        self.append_log("⏳ 正在启动 scrcpy，投屏窗口马上出现...\n")

        self.scrcpy_process = QProcess(self)
        self.scrcpy_process.setProgram(cmd[0])
        self.scrcpy_process.setArguments(cmd[1:])
        if scrcpy != "scrcpy":
            self.scrcpy_process.setWorkingDirectory(os.path.dirname(scrcpy))
        self.scrcpy_process.readyReadStandardOutput.connect(self._scrcpy_stdout)
        self.scrcpy_process.readyReadStandardError.connect(self._scrcpy_stderr)
        self.scrcpy_process.finished.connect(
            lambda code, status: self._scrcpy_finished(code, wireless_serial)
        )
        self.scrcpy_process.start()

        self.btn_launch_scrcpy.setEnabled(False)
        self.btn_stop_scrcpy.setEnabled(True)
        self.status.showMessage("🎮 scrcpy 投屏已启动")

    def _scrcpy_stdout(self):
        if self.scrcpy_process:
            data = self.scrcpy_process.readAllStandardOutput().data().decode("utf-8", "replace")
            if data.strip():
                self.append_log(data.strip())

    def _scrcpy_stderr(self):
        if self.scrcpy_process:
            data = self.scrcpy_process.readAllStandardError().data().decode("utf-8", "replace")
            if data.strip():
                self.append_log(data.strip())

    def _scrcpy_finished(self, code, wireless_serial):
        self.append_log(f"\n🛑 scrcpy 已退出（exit code = {code}）")
        self.btn_launch_scrcpy.setEnabled(True)
        self.btn_stop_scrcpy.setEnabled(False)
        self.status.showMessage("scrcpy 已停止")
        if wireless_serial:
            ok, out = run_cmd([ADB, "disconnect", wireless_serial], timeout=10)
            self.append_log(f"$ adb disconnect {wireless_serial}\n{out}")

    def stop_scrcpy(self):
        if self.scrcpy_process and self.scrcpy_process.state() != QProcess.NotRunning:
            self.append_log("🛑 正在停止 scrcpy...")
            self.scrcpy_process.kill()

    # ---------- 样式 ----------
    def load_qss(self):
        return """
        QMainWindow { background: #f1f5f9; }
        QWidget { font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif; }

        #LeftPanel {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #0f172a, stop:1 #1e293b);
            border: none;
        }
        #LogoWrap {
            background: transparent;
            border-bottom: 1px solid rgba(255,255,255,0.06);
        }
        #LogoText {
            color: #ffffff; font-size: 17px;
            font-weight: bold; letter-spacing: 1px;
        }
        #FuncList {
            background: transparent; border: none; outline: none;
            color: #cbd5e1; padding: 10px 10px;
        }
        #FuncList::item {
            padding: 10px 14px; margin: 2px 0;
            border-radius: 8px; border: none;
        }
        #FuncList::item:hover {
            background: rgba(255,255,255,0.06); color: #ffffff;
        }
        #FuncList::item:selected {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #3b82f6, stop:1 #6366f1);
            color: #ffffff; font-weight: bold;
        }
        #FuncList::item:disabled { color: #475569; background: transparent; }
        #VersionLabel {
            color: #64748b; font-size: 11px;
            border-top: 1px solid rgba(255,255,255,0.06);
        }

        #RightPanel { background: #f1f5f9; }
        #TopBar {
            background: #ffffff;
            border-bottom: 1px solid #e2e8f0;
        }
        #PageTitle { font-size: 18px; font-weight: bold; color: #0f172a; }
        #TopBarLabel { color: #64748b; font-size: 13px; }
        #DeviceCombo {
            border: 1px solid #cbd5e1; border-radius: 8px;
            padding: 8px 14px; font-size: 13px;
            background: #f8fafc; color: #0f172a; min-height: 20px;
        }
        #DeviceCombo:focus { border: 1px solid #3b82f6; background: #ffffff; }
        #BtnRefresh {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #10b981, stop:1 #059669);
            color: white; font-weight: bold; border: none;
            border-radius: 8px; padding: 10px 20px; font-size: 13px;
        }
        #BtnRefresh:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #059669, stop:1 #047857);
        }
        #BtnRefresh:pressed { background: #047857; }

        #ContentWrap { background: #f1f5f9; }
        QLabel { color: #334155; font-size: 13px; }
        #SectionTitle {
            font-size: 15px; font-weight: bold; color: #0f172a;
            padding: 4px 0 10px 0;
        }
        #HintLabel { color: #64748b; font-size: 12px; padding-bottom: 4px; }

        QLineEdit, QComboBox {
            border: 1px solid #cbd5e1; border-radius: 8px;
            padding: 9px 14px; font-size: 13px;
            background: #ffffff; color: #0f172a; min-height: 20px;
        }
        QLineEdit:focus, QComboBox:focus { border: 1px solid #3b82f6; }
        QComboBox::drop-down { border: none; width: 24px; }

        QPushButton {
            background: #ffffff; color: #1e293b;
            border: 1px solid #e2e8f0; border-radius: 8px;
            padding: 11px 20px; font-size: 13px;
        }
        QPushButton:hover { background: #f8fafc; border: 1px solid #cbd5e1; }
        QPushButton:pressed { background: #e2e8f0; }
        QPushButton:disabled {
            background: #e2e8f0; color: #94a3b8; border: 1px solid #e2e8f0;
        }
        #NormalBtn { text-align: left; padding: 13px 20px; }

        #PrimaryBtn {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #3b82f6, stop:1 #6366f1);
            color: white; font-weight: bold; border: none;
            border-radius: 8px; padding: 12px 24px; font-size: 13px;
        }
        #PrimaryBtn:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #2563eb, stop:1 #4f46e5);
        }
        #PrimaryBtn:pressed { background: #1d4ed8; }
        #PrimaryBtn:disabled { background: #cbd5e1; color: #94a3b8; }

        #DangerBtn {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #ef4444, stop:1 #dc2626);
            color: white; font-weight: bold; border: none;
            border-radius: 8px; padding: 12px 24px; font-size: 13px;
        }
        #DangerBtn:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #dc2626, stop:1 #b91c1c);
        }
        #DangerBtn:pressed { background: #b91c1c; }

        #OutputArea {
            background: #0f172a; color: #67e8f9;
            border: 1px solid #1e293b; border-radius: 10px;
            padding: 12px; font-family: "Consolas", "Monaco", monospace;
            selection-background-color: #3b82f6;
        }

        #Banner {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #eff6ff, stop:1 #f5f3ff);
            border: 1px solid #dbeafe; border-radius: 12px;
        }
        #BannerTitle { font-size: 15px; font-weight: bold; color: #1e40af; }
        #BannerSub { font-size: 12px; color: #475569; }

        #InfoScroll { background: transparent; }
        #InfoContainer { background: transparent; }
        #InfoCard {
            background: #ffffff;
            border: 1px solid #e2e8f0; border-radius: 12px;
        }
        #InfoCard:hover { border: 1px solid #93c5fd; background: #f8fbff; }
        #CardTitle { color: #64748b; font-size: 12px; font-weight: normal; }
        #CardValue { color: #0f172a; font-size: 15px; font-weight: bold; }
        #GroupTitle {
            color: #1e293b; font-size: 14px; font-weight: bold;
            padding: 14px 4px 4px 4px;
        }

        QGroupBox#OptBox {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 16px 14px 12px 14px;
            margin-top: 10px;
            font-size: 13px;
            color: #0f172a;
        }
        QGroupBox#OptBox::title {
            subcontrol-origin: margin;
            left: 12px;
            top: 2px;
            padding: 0 6px;
            color: #475569;
            font-weight: bold;
        }
        QCheckBox {
            spacing: 8px;
            color: #334155;
            font-size: 13px;
        }
        QCheckBox::indicator {
            width: 16px; height: 16px;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            background: #ffffff;
        }
        QCheckBox::indicator:hover { border: 1px solid #3b82f6; }
        QCheckBox::indicator:checked {
            background: #3b82f6;
            border: 1px solid #3b82f6;
        }

        #AppStatusBar {
            background: #ffffff; color: #475569;
            border-top: 1px solid #e2e8f0;
            font-size: 12px; padding-left: 12px;
        }
        #AppStatusBar::item { border: none; }

        QScrollBar:vertical {
            background: transparent; width: 10px; margin: 4px 2px;
        }
        QScrollBar::handle:vertical {
            background: #cbd5e1; border-radius: 5px; min-height: 30px;
        }
        QScrollBar::handle:vertical:hover { background: #94a3b8; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

        QMessageBox { background: #ffffff; }
        QMessageBox QPushButton { min-width: 80px; padding: 8px 18px; }
        """


def main():
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("安卓工具箱")
    win = AdbTool()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()