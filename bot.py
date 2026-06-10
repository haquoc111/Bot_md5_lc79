import os
import json
import hashlib
import random
import string
import asyncio
import aiohttp
from datetime import datetime, timedelta
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# ─── CONFIG ────────────────────────────────────────────────────────────────────
BOT_TOKEN  = "8640872279:AAHmCc9ezSBMjJNA7HEMLmeuWvXb7aRrues"
ADMIN_ID   = 7680266707
ADMIN_TG   = "@cskh09099"
API_URL    = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=fa2eaf73a676b982e7471927c1e0293b"
QR_IMAGE   = "qr_payment.png"        # file QR ảnh gốc bạn upload

# ─── GÓI KEY ──────────────────────────────────────────────────────────────────
PACKAGES = {
    "1ngay":    {"label": "1 Ngày",      "price": "20.000đ",  "hours": 24},
    "1tuan":    {"label": "1 Tuần",      "price": "50.000đ",  "hours": 168},
    "1nam":     {"label": "1 Năm 🔥SALE","price": "99.000đ",  "hours": 8760},
    "vinhvien": {"label": "Vĩnh Viễn",   "price": "150.000đ", "hours": 999999},
    "5h":       {"label": "5 Giờ ⚡",    "price": "10.000đ",  "hours": 5},
}

# ─── STORAGE (đơn giản, dùng JSON files – phù hợp Render free tier) ───────────
DATA_DIR  = "data"
KEY_FILE  = os.path.join(DATA_DIR, "keys.json")
USER_FILE = os.path.join(DATA_DIR, "users.json")
PEND_FILE = os.path.join(DATA_DIR, "pending.json")

os.makedirs(DATA_DIR, exist_ok=True)

def _load(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def _save(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─── KEY HELPERS ──────────────────────────────────────────────────────────────
def gen_key(length=20) -> str:
    chars = string.ascii_uppercase + string.digits
    return "SXD-" + "".join(random.choices(chars, k=length))

def create_key(user_id: int, pkg: str) -> str:
    keys = _load(KEY_FILE)
    # Xóa key cũ của user nếu có
    keys = {k: v for k, v in keys.items() if v.get("user_id") != user_id}
    pkg_info = PACKAGES[pkg]
    new_key  = gen_key()
    expire   = (datetime.now() + timedelta(hours=pkg_info["hours"])).isoformat() \
               if pkg_info["hours"] < 999999 else "never"
    keys[new_key] = {
        "user_id":  user_id,
        "pkg":      pkg,
        "expire":   expire,
        "created":  datetime.now().isoformat(),
    }
    _save(KEY_FILE, keys)
    return new_key

def validate_key(user_id: int) -> bool:
    keys = _load(KEY_FILE)
    for k, v in keys.items():
        if v.get("user_id") == user_id:
            if v.get("expire") == "never":
                return True
            if datetime.fromisoformat(v["expire"]) > datetime.now():
                return True
    return False

def get_user_key_info(user_id: int) -> dict | None:
    keys = _load(KEY_FILE)
    for k, v in keys.items():
        if v.get("user_id") == user_id:
            return {"key": k, **v}
    return None

# ─── PENDING ORDERS ───────────────────────────────────────────────────────────
def save_pending(user_id: int, pkg: str):
    pending = _load(PEND_FILE)
    pending[str(user_id)] = {"pkg": pkg, "time": datetime.now().isoformat()}
    _save(PEND_FILE, pending)

def get_pending(user_id: int) -> dict | None:
    pending = _load(PEND_FILE)
    return pending.get(str(user_id))

def remove_pending(user_id: int):
    pending = _load(PEND_FILE)
    pending.pop(str(user_id), None)
    _save(PEND_FILE, pending)

# ─── MD5 PREDICTION ALGORITHM ─────────────────────────────────────────────────
def md5_predict(md5_hash: str) -> dict:
    """
    Thuật toán dự đoán tài/xỉu từ mã MD5.
    Phân tích hex entropy, position weights, parity pattern.
    """
    h = md5_hash.strip().lower()
    if len(h) != 32 or not all(c in "0123456789abcdef" for c in h):
        return {"error": "Mã MD5 không hợp lệ (cần 32 ký tự hex)"}

    # Chia thành 4 nhóm 8 ký tự
    segments = [h[i:i+8] for i in range(0, 32, 8)]
    seg_vals  = [int(s, 16) for s in segments]

    # Trọng số theo vị trí (segment đầu quan trọng hơn)
    weights   = [0.40, 0.30, 0.20, 0.10]
    weighted  = sum(v * w for v, w in zip(seg_vals, weights))
    max_val   = 0xFFFFFFFF

    # Parity bit của toàn bộ hash
    total_bits = bin(int(h, 16)).count("1")
    parity     = total_bits % 2  # 0=chẵn, 1=lẻ

    # Entropy score (0-1)
    entropy = weighted / max_val

    # Kết hợp entropy + parity
    score = (entropy * 0.7) + (parity * 0.3)

    if score >= 0.5:
        result      = "TÀI 🎲"
        confidence  = int(50 + (score - 0.5) * 100)
    else:
        result      = "XỈU 🎯"
        confidence  = int(50 + (0.5 - score) * 100)

    confidence = min(confidence, 95)  # cap tại 95%

    # Gợi ý xu hướng
    trend = "Mạnh" if confidence >= 75 else "Trung bình" if confidence >= 60 else "Yếu"

    return {
        "result":     result,
        "confidence": confidence,
        "trend":      trend,
        "entropy":    round(entropy * 100, 2),
        "parity":     "Lẻ" if parity else "Chẵn",
    }

# ─── API PREDICTION ───────────────────────────────────────────────────────────
async def fetch_api_data() -> dict:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        return {"error": str(e)}
    return {"error": "Không thể kết nối API"}

def analyze_history(sessions: list) -> dict:
    """
    Phân tích lịch sử để phát hiện cầu và điểm bẻ cầu.
    Trả về dự đoán khôn ngoan.
    """
    if not sessions or len(sessions) < 3:
        return {"result": "TÀI", "confidence": 55, "reason": "Không đủ dữ liệu"}

    results = []
    for s in sessions[:20]:  # Lấy 20 phiên gần nhất
        dice_sum = s.get("diceTotal") or s.get("total") or 0
        if isinstance(dice_sum, (int, float)):
            results.append("TÀI" if dice_sum >= 11 else "XỈU")

    if not results:
        return {"result": "TÀI", "confidence": 55, "reason": "Dữ liệu không hợp lệ"}

    # Đếm streak hiện tại
    current = results[0]
    streak  = 1
    for r in results[1:]:
        if r == current:
            streak += 1
        else:
            break

    # Tỷ lệ tài/xỉu
    tai_count  = results.count("TÀI")
    xiu_count  = results.count("XỈU")
    total      = len(results)

    # Logic bẻ cầu thông minh
    if streak >= 5:
        # Cầu quá dài → bẻ cầu
        prediction  = "XỈU" if current == "TÀI" else "TÀI"
        confidence  = min(75 + streak * 2, 88)
        reason      = f"Bẻ cầu – {current} đã xuất hiện {streak} lần liên tiếp"
    elif streak >= 3:
        # Cầu trung bình → theo cầu nhẹ
        prediction  = current
        confidence  = 65 + streak
        reason      = f"Theo cầu – {current} liên tiếp {streak} lần"
    else:
        # Không có cầu rõ ràng → dựa vào tỷ lệ
        if tai_count > xiu_count * 1.5:
            prediction, confidence = "XỈU", 62
            reason = "Tài xuất hiện quá nhiều, cân bằng về xỉu"
        elif xiu_count > tai_count * 1.5:
            prediction, confidence = "TÀI", 62
            reason = "Xỉu xuất hiện quá nhiều, cân bằng về tài"
        else:
            prediction  = results[0]
            confidence  = 58
            reason      = "Thị trường cân bằng, theo kết quả gần nhất"

    return {
        "result":     prediction,
        "confidence": confidence,
        "reason":     reason,
        "streak":     streak,
        "current_run": current,
        "tai_rate":   round(tai_count / total * 100, 1),
        "xiu_rate":   round(xiu_count / total * 100, 1),
    }

async def get_api_prediction() -> dict:
    data = await fetch_api_data()
    if "error" in data:
        return {"error": data["error"]}

    # Tìm sessions array
    sessions = None
    for key in ["data", "sessions", "result", "list", "items"]:
        if key in data and isinstance(data[key], list):
            sessions = data[key]
            break
    if sessions is None and isinstance(data, list):
        sessions = data

    if not sessions:
        return {"error": "Cấu trúc API không nhận diện được"}

    latest  = sessions[0] if sessions else {}
    prev    = sessions[1] if len(sessions) > 1 else {}

    # Lấy thông tin phiên mới nhất
    phien_id  = latest.get("sessionId") or latest.get("id") or latest.get("sid") or "N/A"
    total     = latest.get("diceTotal") or latest.get("total") or 0
    dice_arr  = latest.get("dice") or latest.get("dices") or []

    if isinstance(dice_arr, list) and len(dice_arr) >= 3:
        dice_str = f"{dice_arr[0]}-{dice_arr[1]}-{dice_arr[2]}"
    elif isinstance(total, (int, float)) and total > 0:
        dice_str = f"Tổng: {int(total)}"
    else:
        dice_str = "N/A"

    ket_qua  = "TÀI" if isinstance(total, (int, float)) and total >= 11 else "XỈU"
    phien_moi = (int(phien_id) + 1) if str(phien_id).isdigit() else f"{phien_id}+1"

    analysis = analyze_history(sessions)

    # Lấy MD5 hash của phiên mới nhất
    md5_latest = latest.get("md5") or latest.get("hash") or ""
    if md5_latest and len(md5_latest) == 32:
        md5_pred  = md5_predict(md5_latest)
        md5_conf  = md5_pred.get("confidence", 55)
        # Kết hợp 2 dự đoán
        if md5_pred.get("result", "").startswith("TÀI") and analysis["result"] == "TÀI":
            final_conf = min(int((analysis["confidence"] + md5_conf) / 2) + 5, 92)
            final_res  = "TÀI"
        elif md5_pred.get("result", "").startswith("XỈU") and analysis["result"] == "XỈU":
            final_conf = min(int((analysis["confidence"] + md5_conf) / 2) + 5, 92)
            final_res  = "XỈU"
        else:
            # Xung đột → tin vào phân tích cầu hơn
            final_conf = analysis["confidence"] - 5
            final_res  = analysis["result"]
    else:
        final_conf = analysis["confidence"]
        final_res  = analysis["result"]

    return {
        "phien":      phien_id,
        "ket_qua":    ket_qua,
        "xuc_xac":    dice_str,
        "phien_moi":  phien_moi,
        "du_doan":    final_res,
        "confidence": final_conf,
        "reason":     analysis["reason"],
        "tai_rate":   analysis.get("tai_rate", 0),
        "xiu_rate":   analysis.get("xiu_rate", 0),
    }

# ─── KEYBOARDS ────────────────────────────────────────────────────────────────
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Dự đoán bằng API",    callback_data="predict_api")],
        [InlineKeyboardButton("🔐 Dự đoán bằng MD5",    callback_data="predict_md5")],
        [InlineKeyboardButton("🔑 Nhập Key sử dụng",    callback_data="enter_key")],
        [InlineKeyboardButton("💳 Bảng giá / Mua Key",  callback_data="buy_key")],
        [InlineKeyboardButton("👤 Thông tin tài khoản", callback_data="my_account")],
    ])

def packages_keyboard():
    btns = []
    for pkg_id, info in PACKAGES.items():
        btns.append([InlineKeyboardButton(
            f"{info['label']} – {info['price']}",
            callback_data=f"buy_{pkg_id}"
        )])
    btns.append([InlineKeyboardButton("⬅️ Quay lại", callback_data="main_menu")])
    return InlineKeyboardMarkup(btns)

def back_keyboard(target="main_menu"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại", callback_data=target)]])

# ─── STATES ───────────────────────────────────────────────────────────────────
WAITING_KEY = 1
WAITING_MD5 = 2
WAITING_BILL = 3

# ─── HANDLERS ─────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"👋 Chào mừng <b>{user.first_name}</b> đến với <b>SXD Prediction Bot</b>!\n\n"
        "🎯 Bot dự đoán Tài/Xỉu thông minh sử dụng:\n"
        "  • Phân tích cầu theo API thời gian thực\n"
        "  • Thuật toán phân tích mã MD5\n\n"
        "⚠️ Cần có <b>Key</b> để sử dụng tính năng dự đoán.\n"
        "Chọn một tùy chọn bên dưới:"
    )
    await update.message.reply_html(text, reply_markup=main_menu_keyboard())

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    # ── Main menu
    if data == "main_menu":
        await query.edit_message_text(
            "🏠 <b>Menu chính</b>\nChọn tính năng bạn muốn sử dụng:",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END

    # ── My account
    elif data == "my_account":
        info = get_user_key_info(user_id)
        if info:
            expire_str = info["expire"] if info["expire"] == "never" else \
                datetime.fromisoformat(info["expire"]).strftime("%d/%m/%Y %H:%M")
            pkg_label  = PACKAGES.get(info["pkg"], {}).get("label", info["pkg"])
            text = (
                f"👤 <b>Tài khoản của bạn</b>\n\n"
                f"🔑 Key: <code>{info['key']}</code>\n"
                f"📦 Gói: {pkg_label}\n"
                f"⏰ Hết hạn: {expire_str}\n"
                f"✅ Trạng thái: {'Còn hạn' if validate_key(user_id) else '❌ Hết hạn'}"
            )
        else:
            text = "❌ Bạn chưa có Key nào.\nHãy mua Key để sử dụng tính năng dự đoán."
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_keyboard())

    # ── Buy key – show packages
    elif data == "buy_key":
        text = (
            "💳 <b>Bảng giá Key</b>\n\n"
            "1️⃣  1 Ngày          –   <b>20.000đ</b>\n"
            "7️⃣  1 Tuần          –   <b>50.000đ</b>\n"
            "🔥  1 Năm (SALE)  –   <b>99.000đ</b>\n"
            "♾️  Vĩnh Viễn       – <b>150.000đ</b>\n"
            "⚡  5 Giờ            –   <b>10.000đ</b>\n\n"
            "👇 Chọn gói bạn muốn mua:"
        )
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=packages_keyboard())

    # ── Confirm package purchase
    elif data.startswith("buy_"):
        pkg = data[4:]
        if pkg not in PACKAGES:
            await query.answer("Gói không hợp lệ!", show_alert=True)
            return
        info = PACKAGES[pkg]
        save_pending(user_id, pkg)
        text = (
            f"💰 <b>Thanh toán gói: {info['label']}</b>\n"
            f"💵 Số tiền: <b>{info['price']}</b>\n\n"
            f"📲 Quét mã QR bên dưới để chuyển khoản.\n"
            f"Nội dung CK: <code>SXD {user_id}</code>\n\n"
            f"✅ Sau khi chuyển khoản, gửi <b>bill/ảnh xác nhận</b> cho bot này.\n"
            f"Admin {ADMIN_TG} sẽ xác nhận và tạo Key cho bạn."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Gửi bill xác nhận", callback_data="send_bill")],
            [InlineKeyboardButton("⬅️ Quay lại", callback_data="buy_key")],
        ])
        # Gửi ảnh QR kèm thông tin
        try:
            with open(QR_IMAGE, "rb") as qr:
                await query.message.reply_photo(
                    photo=qr,
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=kb
                )
            await query.message.delete()
        except FileNotFoundError:
            await query.edit_message_text(
                text + "\n\n⚠️ <i>(Mã QR đang được cập nhật)</i>",
                parse_mode="HTML",
                reply_markup=kb
            )

    # ── Send bill – prompt user
    elif data == "send_bill":
        await query.edit_message_caption(
            caption=(
                "📤 <b>Gửi bill chuyển khoản</b>\n\n"
                "Hãy gửi ảnh chụp màn hình hoặc ảnh bill chuyển khoản vào đây.\n"
                "Bot sẽ chuyển tiếp đến admin để xác nhận."
            ),
            parse_mode="HTML",
            reply_markup=back_keyboard("buy_key")
        )
        ctx.user_data["waiting_bill"] = True

    # ── Enter key
    elif data == "enter_key":
        await query.edit_message_text(
            "🔑 <b>Nhập Key sử dụng</b>\n\nVui lòng gửi Key của bạn (dạng: SXD-XXXX...):",
            parse_mode="HTML",
            reply_markup=back_keyboard()
        )
        return WAITING_KEY

    # ── Predict API
    elif data == "predict_api":
        if not validate_key(user_id):
            await query.edit_message_text(
                "🔒 <b>Tính năng này yêu cầu Key</b>\n\n"
                "Bạn chưa có Key hoặc Key đã hết hạn.\n"
                "Vui lòng mua Key để tiếp tục sử dụng.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💳 Mua Key ngay", callback_data="buy_key")],
                    [InlineKeyboardButton("🔑 Nhập Key",     callback_data="enter_key")],
                    [InlineKeyboardButton("⬅️ Quay lại",     callback_data="main_menu")],
                ])
            )
            return

        await query.edit_message_text(
            "⏳ Đang lấy dữ liệu từ API...",
            parse_mode="HTML"
        )
        pred = await get_api_prediction()

        if "error" in pred:
            text = f"❌ Lỗi kết nối API:\n<code>{pred['error']}</code>"
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_keyboard())
            return

        emoji = "🔴" if pred["du_doan"] == "TÀI" else "⚪"
        text = (
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 <b>Phiên:</b> {pred['phien']}\n"
            f"🎲 <b>Kết quả:</b> {pred['ket_qua']}\n"
            f"🎯 <b>Xúc xắc:</b> {pred['xuc_xac']}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🆕 <b>Phiên mới:</b> {pred['phien_moi']}\n"
            f"{emoji} <b>Dự đoán:</b> {pred['du_doan']}\n"
            f"📊 <b>Độ tin cậy:</b> {pred['confidence']}%\n"
            f"💡 <b>Lý do:</b> {pred['reason']}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 Tài: {pred['tai_rate']}%  |  Xỉu: {pred['xiu_rate']}%\n"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Cập nhật dự đoán", callback_data="predict_api")],
            [InlineKeyboardButton("⬅️ Menu chính",        callback_data="main_menu")],
        ])
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)

    # ── Predict MD5
    elif data == "predict_md5":
        if not validate_key(user_id):
            await query.edit_message_text(
                "🔒 <b>Tính năng này yêu cầu Key</b>\n\n"
                "Bạn chưa có Key hoặc Key đã hết hạn.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💳 Mua Key ngay", callback_data="buy_key")],
                    [InlineKeyboardButton("🔑 Nhập Key",     callback_data="enter_key")],
                    [InlineKeyboardButton("⬅️ Quay lại",     callback_data="main_menu")],
                ])
            )
            return

        await query.edit_message_text(
            "🔐 <b>Dự đoán bằng MD5</b>\n\n"
            "Vui lòng gửi mã MD5 (32 ký tự) để dự đoán:",
            parse_mode="HTML",
            reply_markup=back_keyboard()
        )
        return WAITING_MD5

async def receive_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id  = update.effective_user.id
    key_text = update.message.text.strip()
    keys     = _load(KEY_FILE)

    matched = None
    for k, v in keys.items():
        if k == key_text:
            matched = (k, v)
            break

    if not matched:
        await update.message.reply_html(
            "❌ Key không hợp lệ hoặc không tồn tại.\nVui lòng kiểm tra lại.",
            reply_markup=back_keyboard()
        )
        return WAITING_KEY

    k, v = matched
    # Gán key cho user này
    if v.get("expire") != "never" and datetime.fromisoformat(v["expire"]) <= datetime.now():
        await update.message.reply_html(
            "⏰ Key này đã hết hạn!\nVui lòng mua Key mới.",
            reply_markup=back_keyboard()
        )
        return ConversationHandler.END

    # Reassign key to this user if unassigned or same user
    if v.get("user_id") is None or v.get("user_id") == 0:
        keys[k]["user_id"] = user_id
        _save(KEY_FILE, keys)

    if v.get("user_id") not in (None, 0, user_id):
        await update.message.reply_html(
            "🚫 Key này đã được sử dụng bởi tài khoản khác.",
            reply_markup=back_keyboard()
        )
        return ConversationHandler.END

    keys[k]["user_id"] = user_id
    _save(KEY_FILE, keys)

    expire_str = v["expire"] if v["expire"] == "never" else \
        datetime.fromisoformat(v["expire"]).strftime("%d/%m/%Y %H:%M")
    pkg_label  = PACKAGES.get(v["pkg"], {}).get("label", v["pkg"])

    await update.message.reply_html(
        f"✅ <b>Kích hoạt Key thành công!</b>\n\n"
        f"📦 Gói: {pkg_label}\n"
        f"⏰ Hết hạn: {expire_str}\n\n"
        f"Bạn có thể sử dụng tất cả tính năng dự đoán.",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

async def receive_md5(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id   = update.effective_user.id
    md5_text  = update.message.text.strip()

    if not validate_key(user_id):
        await update.message.reply_html(
            "🔒 Key của bạn đã hết hạn.", reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END

    pred = md5_predict(md5_text)
    if "error" in pred:
        await update.message.reply_html(
            f"❌ {pred['error']}", reply_markup=back_keyboard("predict_md5")
        )
        return WAITING_MD5

    emoji = "🔴" if pred["result"].startswith("TÀI") else "⚪"
    text = (
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🔐 <b>Mã MD5:</b>\n<code>{md5_text}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji} <b>Dự đoán:</b> {pred['result']}\n"
        f"📊 <b>Độ tin cậy:</b> {pred['confidence']}%\n"
        f"📉 <b>Entropy:</b> {pred['entropy']}%\n"
        f"🔢 <b>Parity:</b> {pred['parity']}\n"
        f"💪 <b>Xu hướng:</b> {pred['trend']}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Nhập MD5 khác", callback_data="predict_md5")],
        [InlineKeyboardButton("⬅️ Menu chính",    callback_data="main_menu")],
    ])
    await update.message.reply_html(text, reply_markup=kb)
    return ConversationHandler.END

async def receive_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Nhận bill chuyển khoản từ user và chuyển tiếp đến admin."""
    user    = update.effective_user
    user_id = user.id
    pending = get_pending(user_id)

    if not pending and not ctx.user_data.get("waiting_bill"):
        return  # Không trong trạng thái chờ bill

    pkg_info = PACKAGES.get(pending["pkg"], {}) if pending else {}

    # Chuyển tiếp bill đến admin
    caption_admin = (
        f"📥 <b>Bill chuyển khoản mới</b>\n\n"
        f"👤 User: {user.full_name} (@{user.username or 'N/A'})\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"📦 Gói đặt: {pkg_info.get('label', 'N/A')} – {pkg_info.get('price', 'N/A')}\n\n"
        f"✅ Xác nhận: /confirm_{user_id}_{pending['pkg'] if pending else 'unknown'}\n"
        f"❌ Từ chối:  /reject_{user_id}"
    )
    try:
        await ctx.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=update.message.photo[-1].file_id,
            caption=caption_admin,
            parse_mode="HTML"
        )
    except Exception:
        pass

    ctx.user_data.pop("waiting_bill", None)
    await update.message.reply_html(
        "✅ <b>Đã gửi bill thành công!</b>\n\n"
        f"Admin {ADMIN_TG} sẽ xác nhận và tạo Key cho bạn trong thời gian sớm nhất.\n"
        "Vui lòng chờ thông báo.",
        reply_markup=main_menu_keyboard()
    )

# ─── ADMIN COMMANDS ───────────────────────────────────────────────────────────
async def admin_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    cmd = update.message.text.strip()
    # Format: /confirm_<user_id>_<pkg>
    try:
        parts   = cmd.split("_")
        user_id = int(parts[1])
        pkg     = parts[2]
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Cú pháp: /confirm_<user_id>_<pkg>")
        return

    if pkg not in PACKAGES:
        await update.message.reply_text(f"❌ Gói '{pkg}' không hợp lệ.")
        return

    new_key   = create_key(user_id, pkg)
    pkg_info  = PACKAGES[pkg]
    expire_dt = datetime.now() + timedelta(hours=pkg_info["hours"])
    expire_str = expire_dt.strftime("%d/%m/%Y %H:%M") \
                 if pkg_info["hours"] < 999999 else "Vĩnh viễn"

    remove_pending(user_id)

    # Thông báo user
    try:
        await ctx.bot.send_message(
            chat_id=user_id,
            text=(
                f"🎉 <b>Thanh toán đã được xác nhận!</b>\n\n"
                f"📦 Gói: {pkg_info['label']}\n"
                f"🔑 Key của bạn:\n<code>{new_key}</code>\n"
                f"⏰ Hết hạn: {expire_str}\n\n"
                f"⚠️ Key chỉ dùng được cho tài khoản này.\n"
                f"Vào /start và chọn <b>Nhập Key</b> để kích hoạt."
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass

    await update.message.reply_html(
        f"✅ Đã tạo Key cho user <code>{user_id}</code>\n"
        f"Key: <code>{new_key}</code>\n"
        f"Gói: {pkg_info['label']}"
    )

async def admin_reject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        user_id = int(update.message.text.split("_")[1])
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Cú pháp: /reject_<user_id>")
        return

    remove_pending(user_id)
    try:
        await ctx.bot.send_message(
            chat_id=user_id,
            text=(
                "❌ <b>Thanh toán bị từ chối</b>\n\n"
                "Bill chuyển khoản của bạn không được xác nhận.\n"
                f"Vui lòng liên hệ {ADMIN_TG} để được hỗ trợ."
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await update.message.reply_text(f"✅ Đã từ chối và thông báo user {user_id}.")

async def admin_listkeys(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    keys = _load(KEY_FILE)
    if not keys:
        await update.message.reply_text("Chưa có key nào.")
        return
    lines = ["<b>📋 Danh sách Key</b>\n"]
    for k, v in list(keys.items())[:30]:
        status = "✅" if v.get("expire") == "never" or \
            (v.get("expire") and datetime.fromisoformat(v["expire"]) > datetime.now()) else "❌"
        lines.append(f"{status} <code>{k}</code> | UID:{v.get('user_id','?')} | {v.get('pkg','?')}")
    await update.message.reply_html("\n".join(lines))

async def admin_delkey(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    parts = update.message.text.strip().split(" ", 1)
    if len(parts) < 2:
        await update.message.reply_text("Dùng: /delkey <KEY>")
        return
    keys = _load(KEY_FILE)
    key  = parts[1].strip()
    if key in keys:
        del keys[key]
        _save(KEY_FILE, keys)
        await update.message.reply_text(f"✅ Đã xoá key: {key}")
    else:
        await update.message.reply_text("❌ Không tìm thấy key.")

async def admin_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    parts = update.message.text.strip().split(" ", 1)
    if len(parts) < 2:
        await update.message.reply_text("Dùng: /broadcast <nội dung>")
        return
    msg  = parts[1]
    keys = _load(KEY_FILE)
    uids = set(v.get("user_id") for v in keys.values() if v.get("user_id"))
    ok, fail = 0, 0
    for uid in uids:
        try:
            await ctx.bot.send_message(chat_id=uid, text=f"📢 {msg}")
            ok += 1
        except Exception:
            fail += 1
    await update.message.reply_text(f"✅ Gửi OK: {ok} | Thất bại: {fail}")

# ─── FALLBACK ─────────────────────────────────────────────────────────────────
async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(
        "❌ Đã huỷ.", reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler)],
        states={
            WAITING_KEY:  [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_key)],
            WAITING_MD5:  [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_md5)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(button_handler, pattern="main_menu"),
        ],
        per_message=False,
    )

    app.add_handler(CommandHandler("start",       start))
    app.add_handler(MessageHandler(filters.Regex(r"^/confirm_\d+_\w+$"), admin_confirm))
    app.add_handler(MessageHandler(filters.Regex(r"^/reject_\d+$"),      admin_reject))
    app.add_handler(CommandHandler("listkeys",    admin_listkeys))
    app.add_handler(CommandHandler("delkey",      admin_delkey))
    app.add_handler(CommandHandler("broadcast",   admin_broadcast))
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.PHOTO, receive_photo))

    print("🤖 Bot đang chạy...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
