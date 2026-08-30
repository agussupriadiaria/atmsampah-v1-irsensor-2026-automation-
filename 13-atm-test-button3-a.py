# update ukuran layar dengan yang terbaru

from tkinter import *
from PIL import Image, ImageDraw, ImageTk, ImageFont
import RPi.GPIO as GPIO
import time
import sys
import signal
import random
import qrcode
from datetime import datetime


# ================= KONFIGURASI GPIO =================

BUTTON_PIN1 = 27  # botol
BUTTON_PIN2 = 22  # tutup botol
OUTPUT_PIN = 6    # output ke arduino
START_PIN = 5     # button mulai
EMERGENCY_PIN = 16  # emergency button

GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(BUTTON_PIN2, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(OUTPUT_PIN, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(START_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(EMERGENCY_PIN, GPIO.OUT, initial=GPIO.LOW)


# ================= KONFIGURASI TAMPILAN =================

SAVE_PATH = "/home/aria/Desktop/atmsampah-v1-irsensor-2026/saveData.txt"

POIN_PER_BOTOL = 50

last_state = None
start_busy = False

bottle = 0
saldo = 0
trxId = None


# ================= SIGNAL HANDLER =================

def signal_handler(signum, frame):
    try:
        closeWindow()
    except Exception:
        pass

    sys.exit()


signal.signal(signal.SIGINT, signal_handler)


# ================= BACKGROUND =================

def create_gradient_background(width, height):
    """
    Buat background image dengan gradient hijau.
    Dari bright green (#00FF00) ke hijau lebih gelap (#006600) vertikal.
    """

    img = Image.new('RGB', (width, height))
    pixels = img.load()

    # Warna gradasi:
    # dari bright green di atas ke dark green di bawah
    start_color = (0, 255, 0)      # Bright green (#00FF00)
    end_color = (0, 102, 0)        # Dark green (#006600)

    for y in range(height):
        # Hitung ratio (0 sampai 1)
        ratio = y / height

        # Interpolasi RGB
        r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
        g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
        b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)

        # Set seluruh row dengan warna yang sama
        for x in range(width):
            pixels[x, y] = (r, g, b)

    return img


# ================= FONT =================

def _load_font(size):
    """
    Coba pakai font TrueType agar teks tombol besar tetap proporsional,
    fallback ke font default kalau tidak tersedia di sistem.
    """

    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]

    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue

    return ImageFont.load_default()


# ================= ICON SEDERHANA =================

# Icon dibuat langsung dengan PIL agar tidak membutuhkan file gambar eksternal.
# Ukurannya kecil sehingga ringan untuk Raspberry Pi.

def create_point_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    pad = max(2, size // 12)
    d.ellipse(
        [pad, pad, size - pad, size - pad],
        fill="#f2c94c",
        outline="#b8860b",
        width=max(2, size // 14)
    )

    fnt = _load_font(max(10, int(size * 0.48)))
    text = "P"
    bbox = d.textbbox((0, 0), text, font=fnt)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    d.text(
        ((size - tw) // 2, (size - th) // 2 - max(1, size // 20)),
        text,
        font=fnt,
        fill="#8a6500"
    )

    return ImageTk.PhotoImage(img)


def create_cap_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    d.rounded_rectangle(
        [int(size * 0.16), int(size * 0.28), int(size * 0.84), int(size * 0.74)],
        radius=max(3, size // 10),
        fill="#555555"
    )

    line_w = max(2, size // 14)
    for ratio in (0.40, 0.53, 0.66):
        y = int(size * ratio)
        d.line(
            [int(size * 0.24), y, int(size * 0.76), y],
            fill="white",
            width=line_w
        )

    return ImageTk.PhotoImage(img)


def create_bottle_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Tutup botol
    d.rectangle(
        [int(size * 0.38), int(size * 0.08), int(size * 0.62), int(size * 0.18)],
        fill="#333333"
    )

    # Leher botol
    d.rounded_rectangle(
        [int(size * 0.40), int(size * 0.16), int(size * 0.60), int(size * 0.38)],
        radius=max(2, size // 16),
        fill="#555555"
    )

    # Badan botol
    d.rounded_rectangle(
        [int(size * 0.27), int(size * 0.34), int(size * 0.73), int(size * 0.90)],
        radius=max(4, size // 10),
        fill="#777777",
        outline="#444444",
        width=max(2, size // 18)
    )

    # Garis sederhana pada badan botol
    d.line(
        [int(size * 0.34), int(size * 0.54), int(size * 0.66), int(size * 0.54)],
        fill="white",
        width=max(2, size // 18)
    )

    return ImageTk.PhotoImage(img)


# ================= BUTTON =================

def makeBtn(
    parent,
    text,
    color,
    hover_color,
    cmd,
    x,
    y,
    w=110,
    h=50,
    bg_color="white",
    font_size=None
):

    cvs = Canvas(
        parent,
        width=w,
        height=h,
        bd=0,
        highlightthickness=0,
        bg=bg_color
    )

    cvs.place(x=x, y=y)

    # Ukuran font dibuat 1/3 dari ukuran semula
    if font_size is None:
        font_size = max(4, int(h * 0.22))  # Diubah dari 0.32 menjadi 0.11 (sekitar 1/3)

    def draw(c):
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        d.rounded_rectangle(
            [0, 0, w, h],
            radius=14,
            fill=c
        )

        fnt = _load_font(font_size)

        bbox = d.textbbox(
            (0, 0),
            text,
            font=fnt
        )

        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        d.text(
            ((w - tw) // 2, (h - th) // 2),
            text,
            font=fnt,
            fill="white"
        )

        tk_img = ImageTk.PhotoImage(img)

        cvs.tk_img = tk_img

        cvs.delete("all")

        cvs.create_image(
            0,
            0,
            anchor=NW,
            image=tk_img
        )

    def on_enter(e):
        draw(hover_color)

    def on_leave(e):
        draw(color)

    def on_press(e):
        cvs.place(
            x=x + 3,
            y=y + 3
        )

        draw(color)

    def on_release(e):
        cvs.place(
            x=x,
            y=y
        )

        draw(hover_color)

        cmd()

    draw(color)

    cvs.bind("<Enter>", on_enter)
    cvs.bind("<Leave>", on_leave)
    cvs.bind("<Button-1>", on_press)
    cvs.bind("<ButtonRelease-1>", on_release)

    return cvs


# ================= EMERGENCY BUTTON =================

def emergency_press(event=None):
    GPIO.output(EMERGENCY_PIN, GPIO.HIGH)
    print("[EMERGENCY] GPIO 16 = HIGH")


def emergency_release(event=None):
    GPIO.output(EMERGENCY_PIN, GPIO.LOW)
    print("[EMERGENCY] GPIO 16 = LOW")


# ================= MAIN PAGE =================

def mainPage():

    global root, timeStamp, dateStamp

    global saldoLabel
    global trxIdLabel
    global jumlahLabel
    global statusLabel

    global sensor1Label
    global sensor2Label

    root = Tk()

    # ===== SETUP FULLSCREEN UNTUK RPi =====

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    print(
        f"[DISPLAY] Screen size: "
        f"{screen_width}x{screen_height}"
    )

    root.geometry(
        f"{screen_width}x{screen_height}+0+0"
    )

    root.overrideredirect(True)

    root.config(cursor="none")

    root.title(
        "ATM Sampah - UBGreenCampus"
    )

    root.update()

    print(
        "[DISPLAY] Fullscreen enabled - "
        "kiosk mode with green gradient"
    )


    # === CREATE GRADIENT BACKGROUND ===

    gradient_img = create_gradient_background(
        screen_width,
        screen_height
    )

    gradient_tk = ImageTk.PhotoImage(
        gradient_img
    )

    bg_label = Label(
        root,
        image=gradient_tk
    )

    bg_label.image = gradient_tk

    bg_label.place(
        x=0,
        y=0,
        relwidth=1,
        relheight=1
    )


    # ================= TITLE =================

    titleLabel = Label(
        bg_label,
        text="UB GREENCAMPUS",
        font=("Helvetica", 20, "bold"),
        bg="white",
        fg="darkgreen",
        padx=10,
        pady=5
    )

    titleLabel.place(
        relx=0.5,
        rely=0.08,
        anchor=CENTER
    )


    # ================= MAIN FRAME =================

    mainFrame = Frame(
        root,
        bd=10,
        highlightbackground="green",
        highlightthickness=5,
        bg="white"
    )

    mainFrame.place(
        relx=0.025,
        rely=0.15,
        relwidth=0.95,
        relheight=0.82
    )

    root.update()

    frame_w = mainFrame.winfo_width()
    frame_h = mainFrame.winfo_height()


    # ================= STAMP KIRI ATAS =================

    stampFrame = Frame(
        mainFrame,
        bg="white",
        bd=0
    )

    stampFrame.place(
        x=10,
        y=8
    )

    Label(
        stampFrame,
        text="Waktu  ",
        font=("Helvetica", 10, "bold"),
        bg="white"
    ).grid(
        row=0,
        column=0,
        sticky="w",
        padx=(5, 0),
        pady=(3, 0)
    )

    Label(
        stampFrame,
        text="Tanggal",
        font=("Helvetica", 10, "bold"),
        bg="white"
    ).grid(
        row=1,
        column=0,
        sticky="w",
        padx=(5, 0),
        pady=(0, 3)
    )

    timeStamp = Label(
        stampFrame,
        text="00:00:00",
        font=("Helvetica", 10, "bold"),
        bg="white"
    )

    timeStamp.grid(
        row=0,
        column=1,
        padx=(5, 5),
        pady=(3, 0)
    )

    dateStamp = Label(
        stampFrame,
        text="dd/mm/yy",
        font=("Helvetica", 10, "bold"),
        bg="white"
    )

    dateStamp.grid(
        row=1,
        column=1,
        padx=(5, 5),
        pady=(0, 3)
    )


    # ===================================================================
    # LAYOUT:
    #
    #   - Kartu "Total Saldo" & "Data" di sisi kanan
    #   - Tombol "Mulai" & "E-Struk" di sisi kiri
    #
    # Tombol dibuat 75% dari tinggi kartu dan tetap center
    # secara vertikal terhadap kartu.
    # ===================================================================

    gap_between_sides = int(
        frame_w * 0.05
    )


    # ================= UKURAN BLOK =================

    target_block_h = int(
        frame_h * 0.78
    )

    row_gap = max(
        18,
        int(frame_h * 0.035)
    )

    card_w = int(
        frame_w * 0.38
    )

    # Dua kartu di kanan
    card_h = (
        target_block_h - row_gap
    ) // 2


    # ================= UKURAN TOMBOL =================
    # Tiga tombol dibuat sama besar dan sejajar vertikal.

    btn_w = min(
        int(frame_w * 0.30),
        340
    )

    btn_h = (
        target_block_h - (row_gap * 2)
    ) // 3


    # ================= POSISI HORIZONTAL =================

    total_w = (
        btn_w
        + gap_between_sides
        + card_w
    )

    left_edge_x = (
        frame_w - total_w
    ) // 2

    btn_x = left_edge_x

    cards_x = (
        left_edge_x
        + btn_w
        + gap_between_sides
    )


    # ================= POSISI VERTIKAL =================

    block_start_y = (
        frame_h - target_block_h
    ) // 2

    row1_y = block_start_y

    row2_y = (
        block_start_y
        + card_h
        + row_gap
    )

    # Tiga tombol kiri dibuat sejajar dengan jarak yang sama.
    mulai_y = block_start_y

    estruk_y = (
        mulai_y
        + btn_h
        + row_gap
    )

    emergency_y = (
        estruk_y
        + btn_h
        + row_gap
    )

    saldo_y = row1_y
    data_y = row2_y


    # ================= FONT KARTU =================

    f_title = max(
        13,
        int(card_h * 0.075)
    )

    f_value = max(
        20,
        int(card_h * 0.115)
    )

    f_datalabel = max(
        11,
        int(card_h * 0.05)
    )

    f_datavalue = (
        f_datalabel + 2
    )

    row_step = int(
        card_h * 0.155
    )

    row0_off = int(
        card_h * 0.20
    )

    value_col_x = int(
        card_w * 0.50
    )


    # ================= CARD TOTAL SALDO =================

    saldoFrame = Frame(
        mainFrame,
        bg="white",
        width=card_w,
        height=card_h,
        highlightbackground="blue",
        highlightthickness=5
    )

    saldoFrame.place(
        x=cards_x,
        y=saldo_y
    )

    saldoFrame.pack_propagate(
        False
    )

    Label(
        saldoFrame,
        bg="white",
        text="TOTAL SALDO",
        font=(
            "Helvetica",
            f_title,
            "bold"
        )
    ).place(
        relx=0.5,
        rely=0.09,
        anchor=CENTER
    )

    # Logo poin sederhana
    point_icon_size = max(34, min(58, int(card_h * 0.16)))
    point_icon = create_point_icon(point_icon_size)

    point_icon_label = Label(
        saldoFrame,
        image=point_icon,
        bg="white"
    )
    point_icon_label.image = point_icon
    point_icon_label.place(
        relx=0.18,
        rely=0.55,
        anchor=CENTER
    )

    Label(
        saldoFrame,
        text="Poin",
        font=(
            "Helvetica",
            f_value,
            "bold"
        ),
        bg="white"
    ).place(
        relx=0.38,
        rely=0.55,
        anchor=CENTER
    )

    saldoLabel = Label(
        saldoFrame,
        text="0",
        font=(
            "Helvetica",
            f_value,
            "bold"
        ),
        bg="white"
    )

    saldoLabel.place(
        relx=0.68,
        rely=0.55,
        anchor=CENTER
    )


    # ================= CARD DATA =================

    dataFrame = Frame(
        mainFrame,
        bg="white",
        width=card_w,
        height=card_h,
        highlightbackground="red",
        highlightthickness=5
    )

    dataFrame.place(
        x=cards_x,
        y=data_y
    )

    dataFrame.pack_propagate(
        False
    )

    Label(
        dataFrame,
        bg="white",
        text="DATA",
        font=(
            "Helvetica",
            f_title,
            "bold"
        )
    ).place(
        relx=0.5,
        rely=0.09,
        anchor=CENTER
    )


    # ================= LABEL DATA =================

    data_label_x = int(card_w * 0.12)
    icon_x = int(card_w * 0.025)

    for i, txt in enumerate(
        [
            "TID",
            "Jumlah Botol",
            "Status Transaksi"
        ]
    ):

        Label(
            dataFrame,
            bg="white",
            text=txt,
            font=(
                "Helvetica",
                f_datalabel,
                "bold"
            )
        ).place(
            x=data_label_x,
            y=row0_off + i * row_step
        )

    # Logo tutup dan botol dibuat langsung dengan PIL agar ringan.
    data_icon_size = max(24, min(38, int(card_h * 0.105)))

    cap_icon = create_cap_icon(data_icon_size)
    cap_icon_label = Label(
        dataFrame,
        image=cap_icon,
        bg="white"
    )
    cap_icon_label.image = cap_icon
    cap_icon_label.place(
        x=icon_x,
        y=row0_off + row_step * 3 + (f_datavalue // 2),
        anchor="w"
    )

    Label(
        dataFrame,
        bg="white",
        text="Tutup",
        font=(
            "Helvetica",
            f_datalabel,
            "bold"
        )
    ).place(
        x=data_label_x,
        y=row0_off + row_step * 3
    )

    bottle_icon = create_bottle_icon(data_icon_size)
    bottle_icon_label = Label(
        dataFrame,
        image=bottle_icon,
        bg="white"
    )
    bottle_icon_label.image = bottle_icon
    bottle_icon_label.place(
        x=icon_x,
        y=row0_off + row_step * 4 + (f_datavalue // 2),
        anchor="w"
    )

    Label(
        dataFrame,
        bg="white",
        text="Botol",
        font=(
            "Helvetica",
            f_datalabel,
            "bold"
        )
    ).place(
        x=data_label_x,
        y=row0_off + row_step * 4
    )


    # ================= VALUE DATA =================

    trxIdLabel = Label(
        dataFrame,
        bg="white",
        text="-----",
        font=(
            "Helvetica",
            f_datavalue,
            "bold"
        )
    )

    trxIdLabel.place(
        x=value_col_x,
        y=row0_off
    )


    jumlahLabel = Label(
        dataFrame,
        bg="white",
        text="0",
        font=(
            "Helvetica",
            f_datavalue,
            "bold"
        )
    )

    jumlahLabel.place(
        x=value_col_x,
        y=row0_off + row_step
    )


    statusLabel = Label(
        dataFrame,
        bg="white",
        text="TIDAK AKTIF",
        font=(
            "Helvetica",
            f_datavalue,
            "bold"
        ),
        fg="red"
    )

    statusLabel.place(
        x=value_col_x,
        y=row0_off + row_step * 2
    )


    sensor1Label = Label(
        dataFrame,
        bg="white",
        text="0",
        font=(
            "Helvetica",
            f_datavalue,
            "bold"
        )
    )

    sensor1Label.place(
        x=value_col_x,
        y=row0_off + row_step * 3
    )


    sensor2Label = Label(
        dataFrame,
        bg="white",
        text="0",
        font=(
            "Helvetica",
            f_datavalue,
            "bold"
        )
    )

    sensor2Label.place(
        x=value_col_x,
        y=row0_off + row_step * 4
    )


    # ================= TOMBOL =================

    makeBtn(
        mainFrame,
        "Mulai",
        "#1a7f37",
        "#28a745",
        startPulse,
        btn_x,
        mulai_y,
        btn_w,
        btn_h,
        bg_color="white"
    )

    makeBtn(
        mainFrame,
        "E-Struk",
        "#b8860b",
        "#e0a721",
        resetCounter,
        btn_x,
        estruk_y,
        btn_w,
        btn_h,
        bg_color="white"
    )

    # ================= TOMBOL EMERGENCY =================
    # GPIO 16 HIGH selama tombol ditekan, LOW saat dilepas.

    emergencyBtn = makeBtn(
        mainFrame,
        "Emergency",
        "#cc0000",
        "#ff3333",
        lambda: None,
        btn_x,
        emergency_y,
        btn_w,
        btn_h,
        bg_color="white"
    )

    emergencyBtn.bind("<ButtonPress-1>", emergency_press)
    emergencyBtn.bind("<ButtonRelease-1>", emergency_release)


    mainFrame.lift()
    stampFrame.lift()
    saldoFrame.lift()
    dataFrame.lift()


    updateTime()
    updateDate()
    userIDNum()


# ================= LOGIKA TRANSAKSI =================

def userIDNum():
    """
    Buat TID baru untuk sesi/pelanggan berikutnya.
    """

    global trxId

    trxId = random.randrange(
        10000,
        100000
    )

    trxIdLabel["text"] = str(
        trxId
    )


def bottleCounter():
    """
    Dipanggil saat sensor botol
    (tombol 1 & 2) aktif bersamaan.
    """

    global bottle, saldo

    bottle += 1

    saldo += POIN_PER_BOTOL

    jumlahLabel["text"] = bottle

    saldoLabel["text"] = saldo

    saveData()

    print(
        f"[Botol] Jumlah: {bottle}, "
        f"Saldo: {saldo}, "
        f"TID: {trxId}"
    )


def resetCounter():
    """
    Tombol E-Struk:
    kirim pulsa START_PIN,
    tampilkan QR untuk sesi berjalan,
    lalu reset untuk pelanggan berikutnya.
    """

    global bottle, saldo

    if bottle == 0:
        print(
            "[E-Struk] Belum ada botol masuk, "
            "tidak ada struk untuk dicetak."
        )
        return

    _startPulse(
        START_PIN
    )

    showQRPopup()

    bottle = 0
    saldo = 0

    jumlahLabel["text"] = bottle

    saldoLabel["text"] = saldo

    userIDNum()

    print(
        "Reset Jumlah Botol dan Saldo "
        "untuk sesi baru"
    )


# ================= QR POPUP =================

def showQRPopup():
    """
    Tampilkan QR code popup dengan auto-close.
    """

    date_now = datetime.now().strftime(
        "%d/%m/%Y"
    )

    url = (
        f"https://pilahsampah.com/transaction/"
        f"?code={trxId}"
        f"&date={date_now}"
        f"&point={saldo}"
    )

    qr = qrcode.QRCode(
        box_size=6,
        border=4
    )

    qr.add_data(url)

    qr.make(
        fit=True
    )

    qr_img = qr.make_image(
        fill_color="black",
        back_color="white"
    )


    overlay = Frame(
        root,
        bg="white",
        bd=5,
        highlightbackground="black",
        highlightthickness=2
    )

    overlay.place(
        relx=0.5,
        rely=0.5,
        anchor=CENTER,
        width=400,
        height=460
    )

    overlay.lift()


    Label(
        overlay,
        text="* Scan kode ini dari HP untuk klaim poin",
        font=("Helvetica", 11, "bold"),
        bg="white"
    ).pack(
        pady=(20, 0)
    )


    Label(
        overlay,
        text="* Kode akan hilang dalam 20 detik",
        font=("Helvetica", 11, "bold"),
        fg="red",
        bg="white"
    ).pack(
        pady=(0, 0)
    )


    tk_img = ImageTk.PhotoImage(
        qr_img
    )

    qr_label = Label(
        overlay,
        image=tk_img,
        bg="white"
    )

    qr_label.image = tk_img

    qr_label.pack(
        pady=10
    )


    Button(
        overlay,
        text="Tutup",
        font=("Helvetica", 10, "bold"),
        bg="red",
        fg="white",
        width=10,
        command=overlay.destroy
    ).pack(
        pady=15
    )


    overlay.after(
        20000,
        overlay.destroy
    )

    print(
        f"[QR] URL: {url}"
    )


# ================= SAVE DATA =================

def saveData():
    """
    Simpan data transaksi ke file.
    """

    time_now = datetime.now().strftime(
        "%H:%M:%S"
    )

    date_now = datetime.now().strftime(
        "%Y-%m-%d"
    )

    try:

        with open(
            SAVE_PATH,
            'a'
        ) as fb:

            fb.write(
                f"{trxId} / "
                f"{time_now} / "
                f"{date_now} / "
                f"{bottle} / "
                f"{saldo}\n"
            )

    except Exception as e:

        print(
            f"[saveData] Gagal menyimpan "
            f"data lokal: {e}"
        )


# ================= GPIO PULSE UNTUK TOMBOL =================

def startPulse():

    _startPulse(
        START_PIN
    )


def _startPulse(pin):

    global start_busy

    if start_busy:
        return

    start_busy = True

    GPIO.output(
        pin,
        GPIO.HIGH
    )

    root.after(
        500,
        lambda: stopPulse(pin)
    )


def stopPulse(pin):

    global start_busy

    GPIO.output(
        pin,
        GPIO.LOW
    )

    start_busy = False


# ================= JAM & TANGGAL =================

def updateTime():

    timeStamp.config(
        text=time.strftime("%H:%M:%S")
    )

    timeStamp.after(
        1000,
        updateTime
    )


def updateDate():

    dateStamp.config(
        text=time.strftime("%d-%m-%Y")
    )

    dateStamp.after(
        86400000,
        updateDate
    )


# ================= POLLING SENSOR BOTOL =================

def pollButtons():

    global last_state

    state1 = GPIO.input(
        BUTTON_PIN1
    )

    state2 = GPIO.input(
        BUTTON_PIN2
    )

    output = (
        state1 == GPIO.LOW
        and
        state2 == GPIO.LOW
    )


    sensor1Val = (
        1 if state1 == GPIO.LOW else 0
    )

    sensor2Val = (
        1 if state2 == GPIO.LOW else 0
    )


    sensor1Label.config(
        text=str(sensor1Val)
    )

    sensor2Label.config(
        text=str(sensor2Val)
    )


    if output != last_state:

        last_state = output

        if output:

            statusLabel.config(
                text="Valid",
                fg="green"
            )

            bottleCounter()

        else:

            statusLabel.config(
                text="Tidak Valid",
                fg="red"
            )


    GPIO.output(
        OUTPUT_PIN,
        GPIO.LOW if output else GPIO.HIGH
    )

    root.after(
        50,
        pollButtons
    )


# ================= CLOSE WINDOW =================

def closeWindow():
    """
    Graceful shutdown.
    """

    GPIO.output(
        OUTPUT_PIN,
        GPIO.HIGH
    )

    GPIO.output(
        START_PIN,
        GPIO.LOW
    )

    GPIO.output(
        EMERGENCY_PIN,
        GPIO.LOW
    )

    GPIO.cleanup()

    root.destroy()


# ================= MAIN STARTUP =================

print("=" * 60)

print(
    "ATM SAMPAH - Starting with "
    "Green Gradient Background..."
)

print("=" * 60)


mainPage()

root.after(
    50,
    pollButtons
)

root.protocol(
    "WM_DELETE_WINDOW",
    closeWindow
)

root.mainloop()