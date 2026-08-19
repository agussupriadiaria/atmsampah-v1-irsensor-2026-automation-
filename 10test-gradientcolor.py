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
BUTTON_PIN1 = 27 #botol
BUTTON_PIN2 = 22 #tutup botol
OUTPUT_PIN  = 6  #output ke arduino
START_PIN = 5 #button mulai

GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(BUTTON_PIN2, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(OUTPUT_PIN, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(START_PIN, GPIO.OUT, initial=GPIO.LOW)

# ================= KONFIGURASI TAMPILAN =================
SAVE_PATH = "/home/aria/Desktop/atmsampah-v1-irsensor-2026/saveData.txt"

POIN_PER_BOTOL = 50

last_state = None
start_busy = False

bottle = 0
saldo  = 0
trxId  = None


def signal_handler(signum, frame):
    try:
        closeWindow()
    except Exception:
        pass
    sys.exit()


signal.signal(signal.SIGINT, signal_handler)


def create_gradient_background(width, height):
    """
    Buat background image dengan gradient hijau.
    Dari bright green (#00FF00) ke hijau lebih gelap (#006600) vertikal.
    """
    img = Image.new('RGB', (width, height))
    pixels = img.load()
    
    # Warna gradasi: dari bright green di atas ke dark green di bawah
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


def makeBtn(parent, text, color, hover_color, cmd, x, y, w=110, h=50, bg_color="white"):
    cvs = Canvas(parent, width=w, height=h, bd=0, highlightthickness=0, bg=bg_color)
    cvs.place(x=x, y=y)

    def draw(c):
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, w, h], radius=10, fill=c)
        fnt = ImageFont.load_default()
        bbox = d.textbbox((0, 0), text, font=fnt)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        d.text(((w - tw) // 2, (h - th) // 2), text, font=fnt, fill="white")
        tk_img = ImageTk.PhotoImage(img)
        cvs.tk_img = tk_img
        cvs.delete("all")
        cvs.create_image(0, 0, anchor=NW, image=tk_img)

    def on_enter(e):
        draw(hover_color)

    def on_leave(e):
        draw(color)

    def on_press(e):
        cvs.place(x=x + 3, y=y + 3)
        draw(color)

    def on_release(e):
        cvs.place(x=x, y=y)
        draw(hover_color)
        cmd()

    draw(color)
    cvs.bind("<Enter>", on_enter)
    cvs.bind("<Leave>", on_leave)
    cvs.bind("<Button-1>", on_press)
    cvs.bind("<ButtonRelease-1>", on_release)
    return cvs


def mainPage():
    global root, timeStamp, dateStamp
    global saldoLabel, trxIdLabel, jumlahLabel, statusLabel
    global sensor1Label, sensor2Label

    root = Tk()
    
    # ===== SETUP FULLSCREEN UNTUK RPi ======
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    
    print(f"[DISPLAY] Screen size: {screen_width}x{screen_height}")
    
    root.geometry(f"{screen_width}x{screen_height}+0+0")
    root.overrideredirect(True)
    root.config(cursor="none")
    root.title("ATM Sampah - UBGreenCampus")
    root.update()
    
    print("[DISPLAY] Fullscreen enabled - kiosk mode with green gradient")

    # === CREATE GRADIENT BACKGROUND ===
    gradient_img = create_gradient_background(screen_width, screen_height)
    gradient_tk = ImageTk.PhotoImage(gradient_img)
    
    bg_label = Label(root, image=gradient_tk)
    bg_label.image = gradient_tk
    bg_label.place(x=0, y=0, relwidth=1, relheight=1)
    
    # Title
    titleLabel = Label(bg_label, text="UB GREENCAMPUS", font=("Helvetica", 20, "bold"), 
                       bg="white", fg="darkgreen", padx=10, pady=5)
    titleLabel.place(relx=0.5, rely=0.08, anchor=CENTER)

    # === MAIN FRAME ===
    mainFrame = Frame(root, bd=10, highlightbackground="green", highlightthickness=5, bg="white")
    mainFrame.place(relx=0.025, rely=0.15, relwidth=0.95, relheight=0.82)
    root.update()
    frame_w = mainFrame.winfo_width()
    frame_h = mainFrame.winfo_height()

    # === STAMP kiri atas (waktu & tanggal) ===
    stampFrame = Frame(mainFrame, bg="white", bd=0)
    stampFrame.place(x=10, y=8)
    Label(stampFrame, text="Waktu  ", font=("Helvetica", 10, "bold"), bg="white").grid(
        row=0, column=0, sticky="w", padx=(5, 0), pady=(3, 0))
    Label(stampFrame, text="Tanggal", font=("Helvetica", 10, "bold"), bg="white").grid(
        row=1, column=0, sticky="w", padx=(5, 0), pady=(0, 3))
    timeStamp = Label(stampFrame, text="00:00:00", font=("Helvetica", 10, "bold"), bg="white")
    timeStamp.grid(row=0, column=1, padx=(5, 5), pady=(3, 0))
    dateStamp = Label(stampFrame, text="dd/mm/yy", font=("Helvetica", 10, "bold"), bg="white")
    dateStamp.grid(row=1, column=1, padx=(5, 5), pady=(0, 3))

    # === UKURAN & POSISI CARD ===
    card_w = int(frame_w * 0.38)
    card_h = 260
    gap = int(frame_w * 0.04)
    total_w = card_w * 2 + gap
    card_y = (frame_h - card_h - 100) // 2 + 20
    left_x = (frame_w - total_w) // 2
    right_x = left_x + card_w + gap

    # === CARD KIRI: TOTAL SALDO ===
    saldoFrame = Frame(mainFrame, bg="white", width=card_w, height=card_h,
                        highlightbackground="blue", highlightthickness=5)
    saldoFrame.place(x=left_x, y=card_y)
    saldoFrame.pack_propagate(False)
    Label(saldoFrame, bg="white", text="TOTAL SALDO", font=("Helvetica", 15, "bold")).place(
        relx=0.5, y=18, anchor=CENTER)
    Label(saldoFrame, text="Poin", font=("Helvetica", 28, "bold"), bg="white").place(
        relx=0.28, rely=0.5, anchor=CENTER)
    saldoLabel = Label(saldoFrame, text="0", font=("Helvetica", 28, "bold"), bg="white")
    saldoLabel.place(relx=0.65, rely=0.5, anchor=CENTER)

    # === CARD KANAN: DATA ===
    dataFrame = Frame(mainFrame, bg="white", width=card_w, height=card_h,
                       highlightbackground="red", highlightthickness=5)
    dataFrame.place(x=right_x, y=card_y)
    dataFrame.pack_propagate(False)
    Label(dataFrame, bg="white", text="DATA", font=("Helvetica", 15, "bold")).place(
        relx=0.5, y=18, anchor=CENTER)
    for i, txt in enumerate(["TID", "Jumlah Botol", "Status Transaksi", "Tutup", "Botol"]):
        Label(dataFrame, bg="white", text=txt, font=("Helvetica", 11, "bold")).place(x=20, y=53 + i * 40)
    trxIdLabel = Label(dataFrame, bg="white", text="-----", font=("Helvetica", 14, "bold"))
    trxIdLabel.place(x=170, y=51)
    jumlahLabel = Label(dataFrame, bg="white", text="0", font=("Helvetica", 14, "bold"))
    jumlahLabel.place(x=170, y=91)
    statusLabel = Label(dataFrame, bg="white", text="TIDAK AKTIF", font=("Helvetica", 14, "bold"), fg="red")
    statusLabel.place(x=170, y=131)
    sensor1Label = Label(dataFrame, bg="white", text="0", font=("Helvetica", 14, "bold"))
    sensor1Label.place(x=170, y=171)
    sensor2Label = Label(dataFrame, bg="white", text="0", font=("Helvetica", 14, "bold"))
    sensor2Label.place(x=170, y=211)

    # === TOMBOL ===
    btn_w = 110
    btn_h = 50
    spacing = 16
    btn_y = card_y + card_h + 18

    total_btn_w = btn_w * 2 + spacing * 1
    start_x0 = left_x + (total_w - total_btn_w) // 2
    mulai_x = start_x0
    estruk_x = mulai_x + btn_w + spacing

    makeBtn(mainFrame, "Mulai", "#1a7f37", "#28a745", startPulse, mulai_x, btn_y, btn_w, btn_h, bg_color="white")
    makeBtn(mainFrame, "E-Struk", "#b8860b", "#e0a721", resetCounter, estruk_x, btn_y, btn_w, btn_h, bg_color="white")

    mainFrame.lift()
    stampFrame.lift()
    saldoFrame.lift()
    dataFrame.lift()

    updateTime()
    updateDate()
    userIDNum()


# ================= LOGIKA TRANSAKSI =================

def userIDNum():
    """Buat TID baru untuk sesi/pelanggan berikutnya."""
    global trxId
    trxId = random.randrange(10000, 100000)
    trxIdLabel["text"] = str(trxId)


def bottleCounter():
    """Dipanggil saat sensor botol (tombol 1 & 2) aktif bersamaan."""
    global bottle, saldo
    bottle += 1
    saldo += POIN_PER_BOTOL
    jumlahLabel["text"] = bottle
    saldoLabel["text"] = saldo
    saveData()
    print(f"[Botol] Jumlah: {bottle}, Saldo: {saldo}, TID: {trxId}")


def resetCounter():
    """Tombol E-Struk: tampilkan QR untuk sesi berjalan, lalu reset untuk pelanggan berikutnya."""
    global bottle, saldo
    if bottle == 0:
        print("[E-Struk] Belum ada botol masuk, tidak ada struk untuk dicetak.")
        return
    showQRPopup()
    bottle = 0
    saldo = 0
    jumlahLabel["text"] = bottle
    saldoLabel["text"] = saldo
    userIDNum()
    print("Reset Jumlah Botol dan Saldo untuk sesi baru")


def showQRPopup():
    """Tampilkan QR code popup dengan auto-close."""
    date_now = datetime.now().strftime("%d/%m/%Y")
    url = f"https://pilahsampah.com/transaction/?code={trxId}&date={date_now}&point={saldo}"
    qr = qrcode.QRCode(box_size=6, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    overlay = Frame(root, bg="white", bd=5, highlightbackground="black", highlightthickness=2)
    overlay.place(relx=0.5, rely=0.5, anchor=CENTER, width=400, height=460)
    overlay.lift()
    
    Label(overlay, text="* Scan kode ini dari HP untuk klaim poin", font=("Helvetica", 11, "bold"), bg="white").pack(pady=(20, 0))
    Label(overlay, text="* Kode akan hilang dalam 20 detik", font=("Helvetica", 11, "bold"), fg="red", bg="white").pack(pady=(0, 0))
    
    tk_img = ImageTk.PhotoImage(qr_img)
    qr_label = Label(overlay, image=tk_img, bg="white")
    qr_label.image = tk_img
    qr_label.pack(pady=10)
    
    Button(overlay, text="Tutup", font=("Helvetica", 10, "bold"), bg="red", fg="white", width=10,
           command=overlay.destroy).pack(pady=15)
    
    overlay.after(20000, overlay.destroy)
    print(f"[QR] URL: {url}")


def saveData():
    """Simpan data transaksi ke file."""
    time_now = datetime.now().strftime("%H:%M:%S")
    date_now = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(SAVE_PATH, 'a') as fb:
            fb.write(f"{trxId} / {time_now} / {date_now} / {bottle} / {saldo}\n")
    except Exception as e:
        print(f"[saveData] Gagal menyimpan data lokal: {e}")


# ================= GPIO PULSE UNTUK TOMBOL MULAI =================

def startPulse():
    _startPulse(START_PIN)


def _startPulse(pin):
    global start_busy
    if start_busy:
        return
    start_busy = True
    GPIO.output(pin, GPIO.HIGH)
    root.after(500, lambda: stopPulse(pin))


def stopPulse(pin):
    global start_busy
    GPIO.output(pin, GPIO.LOW)
    start_busy = False


# ================= JAM & TANGGAL =================

def updateTime():
    timeStamp.config(text=time.strftime("%H:%M:%S"))
    timeStamp.after(1000, updateTime)


def updateDate():
    dateStamp.config(text=time.strftime("%d-%m-%Y"))
    dateStamp.after(86400000, updateDate)


# ================= POLLING SENSOR BOTOL =================

def pollButtons():
    global last_state

    state1 = GPIO.input(BUTTON_PIN1)
    state2 = GPIO.input(BUTTON_PIN2)
    output = (state1 == GPIO.LOW) and (state2 == GPIO.LOW)

    sensor1Val = 1 if state1 == GPIO.LOW else 0
    sensor2Val = 1 if state2 == GPIO.LOW else 0
    sensor1Label.config(text=str(sensor1Val))
    sensor2Label.config(text=str(sensor2Val))

    if output != last_state:
        last_state = output
        if output:
            statusLabel.config(text="Valid", fg="green")
            bottleCounter()
        else:
            statusLabel.config(text="Tidak Valid", fg="red")

    GPIO.output(OUTPUT_PIN, GPIO.LOW if output else GPIO.HIGH)
    root.after(50, pollButtons)


def closeWindow():
    """Graceful shutdown."""
    GPIO.output(OUTPUT_PIN, GPIO.HIGH)
    GPIO.output(START_PIN, GPIO.LOW)
    GPIO.cleanup()
    root.destroy()


# ================= MAIN STARTUP =================
print("=" * 60)
print("ATM SAMPAH - Starting with Green Gradient Background...")
print("=" * 60)

mainPage()
root.after(50, pollButtons)
root.protocol("WM_DELETE_WINDOW", closeWindow)
root.mainloop()
