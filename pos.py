import customtkinter as ctk
from tkinter import ttk, messagebox, Menu, filedialog, simpledialog
import sqlite3
import hashlib
import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from PIL import Image
from fpdf import FPDF
import os
import subprocess
import cv2
from pyzbar.pyzbar import decode
import socketio
import stripe
import smtplib
from email.mime.text import MIMEText

# Configuration
ctk.set_default_color_theme("blue")
stripe.api_key = "your_stripe_api_key_here"  # Replace with your Stripe API key

# Database Setup
conn = sqlite3.connect('shop.db')
cursor = conn.cursor()

# Create tables
tables = [
    '''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        quantity INTEGER NOT NULL CHECK(quantity >= 0),
        price REAL NOT NULL CHECK(price >= 0),
        supplier_id INTEGER,
        min_stock INTEGER NOT NULL DEFAULT 5 CHECK(min_stock >= 0),
        image_path TEXT,
        barcode TEXT,
        discount REAL DEFAULT 0 CHECK(discount >= 0 AND discount <= 100),
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
    )''',
    '''CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        loyalty_points INTEGER DEFAULT 0 CHECK(loyalty_points >= 0),
        notes TEXT
    )''',
    '''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT,
        email TEXT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('staff', 'admin')) DEFAULT 'staff'
    )''',
    '''CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        total REAL NOT NULL CHECK(total >= 0),
        discount REAL DEFAULT 0 CHECK(discount >= 0 AND discount <= 100),
        payment_method TEXT,
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    )''',
    '''CREATE TABLE IF NOT EXISTS sale_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL CHECK(quantity > 0),
        price REAL NOT NULL CHECK(price >= 0),
        FOREIGN KEY (sale_id) REFERENCES sales(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    )''',
    '''CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        contact TEXT,
        email TEXT,
        products TEXT
    )''',
    '''CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        category TEXT NOT NULL,
        amount REAL NOT NULL CHECK(amount >= 0),
        description TEXT
    )''',
    '''CREATE TABLE IF NOT EXISTS purchase_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('Pending', 'Completed', 'Cancelled')),
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
    )''',
    '''CREATE TABLE IF NOT EXISTS purchase_order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        po_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL CHECK(quantity > 0),
        FOREIGN KEY (po_id) REFERENCES purchase_orders(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    )''',
    '''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''',
    '''CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        user TEXT NOT NULL,
        action TEXT NOT NULL,
        details TEXT
    )'''
]

for table in tables:
    cursor.execute(table)

# Add new columns if they don't exist
cursor.execute("PRAGMA table_info(products)")
columns = [row[1] for row in cursor.fetchall()]
if 'image_path' not in columns:
    cursor.execute("ALTER TABLE products ADD COLUMN image_path TEXT")
if 'barcode' not in columns:
    cursor.execute("ALTER TABLE products ADD COLUMN barcode TEXT")
if 'discount' not in columns:
    cursor.execute("ALTER TABLE products ADD COLUMN discount REAL DEFAULT 0 CHECK(discount >= 0 AND discount <= 100)")

cursor.execute("PRAGMA table_info(customers)")
columns = [row[1] for row in cursor.fetchall()]
if 'notes' not in columns:
    cursor.execute("ALTER TABLE customers ADD COLUMN notes TEXT")

cursor.execute("PRAGMA table_info(users)")
columns = [row[1] for row in cursor.fetchall()]
if 'full_name' not in columns:
    cursor.execute("ALTER TABLE users ADD COLUMN full_name TEXT")
if 'email' not in columns:
    cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")

cursor.execute("PRAGMA table_info(sales)")
columns = [row[1] for row in cursor.fetchall()]
if 'payment_method' not in columns:
    cursor.execute("ALTER TABLE sales ADD COLUMN payment_method TEXT")

conn.commit()

# Real-Time WebSocket Setup
sio = socketio.Server()

@sio.event
def connect(sid, environ):
    print('Client connected:', sid)

@sio.event
def disconnect(sid):
    print('Client disconnected:', sid)

@sio.event
def update_inventory(sid, data):
    cursor.execute("UPDATE products SET quantity=? WHERE id=?", (data['quantity'], data['id']))
    conn.commit()
    sio.emit('inventory_updated', data)

@sio.event
def sale_made(sid, data):
    sio.emit('new_sale', data)

@sio.event
def new_purchase_order(sid, data):
    sio.emit('new_purchase_order', data)

@sio.event
def purchase_order_updated(sid, data):
    sio.emit('purchase_order_updated', data)

# Login Window
class LoginWindow:
    def __init__(self):
        self.window = ctk.CTk()
        self.window.title("Shop Management System - Login")
        self.window.geometry("400x400")
        self.window.resizable(False, False)

        ctk.CTkLabel(self.window, text="My Shop", font=("Arial", 30, "bold")).pack(pady=20)

        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            self.show_first_run()
        else:
            self.show_login()

        self.window.mainloop()

    def show_first_run(self):
        self.window.minsize(400, 400)
        self.window.resizable(True, True)
        
        frame = ctk.CTkFrame(self.window, fg_color="transparent")
        frame.pack(pady=20, padx=20, fill="both", expand=True)

        ctk.CTkLabel(frame, text="Create Admin Account", font=("Arial", 20, "bold")).pack(pady=12)

        self.username = ctk.CTkEntry(frame, placeholder_text="Username", width=400, height=50, font=("Arial", 20))
        self.username.pack(pady=12)

        self.password = ctk.CTkEntry(frame, placeholder_text="Password", show="*", width=400, height=50, font=("Arial", 20))
        self.password.pack(pady=12)

        self.confirm_password = ctk.CTkEntry(frame, placeholder_text="Confirm Password", show="*", width=400, height=50, font=("Arial", 20))
        self.confirm_password.pack(pady=12)

        ctk.CTkButton(frame, text="Create Account", command=self.create_admin, width=400, height=50, font=("Arial", 20)).pack(pady=12)
        ctk.CTkButton(frame, text="Already have an account? Login", command=self.switch_to_login, width=400, height=50, font=("Arial", 20)).pack(pady=12)

    def switch_to_login(self):
        for widget in self.window.winfo_children():
            widget.destroy()
        ctk.CTkLabel(self.window, text="My Shop", font=("Arial", 30, "bold")).pack(pady=20)
        self.show_login()

    def show_login(self):
        frame = ctk.CTkFrame(self.window, fg_color="transparent")
        frame.pack(pady=20, padx=20, fill="both", expand=True)

        ctk.CTkLabel(frame, text="Login", font=("Arial", 20, "bold")).pack(pady=20)

        self.username = ctk.CTkEntry(frame, placeholder_text="Username", width=400, height=50, font=("Arial", 20))
        self.username.pack(pady=12)

        self.password = ctk.CTkEntry(frame, placeholder_text="Password", show="*", width=400, height=50, font=("Arial", 20))
        self.password.pack(pady=12)

        ctk.CTkButton(frame, text="Login", command=self.login, width=400, height=50, font=("Arial", 20)).pack(pady=12)
        ctk.CTkButton(frame, text="Exit", command=self.window.destroy, width=400, height=50, font=("Arial", 20)).pack(pady=12)

    def create_admin(self):
        username = self.username.get().strip()
        password = self.password.get()
        confirm = self.confirm_password.get()

        if not all([username, password, confirm]):
            messagebox.showerror("Error", "All fields are required")
            return

        if password != confirm:
            messagebox.showerror("Error", "Passwords do not match")
            return

        if len(password) < 6:
            messagebox.showerror("Error", "Password must be at least 6 characters")
            return

        hashed = hashlib.sha256(password.encode()).hexdigest()
        try:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, hashed, 'admin'))
            conn.commit()
            messagebox.showinfo("Success", "Admin account created")
            self.window.destroy()
            MainApp('admin', username)
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Username already exists")

    def login(self):
        username = self.username.get().strip()
        password = self.password.get()

        if not all([username, password]):
            messagebox.showerror("Error", "Username and password are required")
            return

        hashed = hashlib.sha256(password.encode()).hexdigest()
        cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, hashed))
        user = cursor.fetchone()

        if user:
            self.window.destroy()
            MainApp(user[5], user[3])  # role and username
        else:
            messagebox.showerror("Error", "Invalid credentials")

# Main Application
class MainApp:
    def __init__(self, role='staff', username=''):
        self.window = ctk.CTk()
        self.window.title("Shop Management System")
        self.window.geometry("1200x800")
        self.role = role
        self.username = username
        self.product_image_filename = None
        self.sio = sio

        # Load appearance mode
        appearance_mode = self.get_setting('appearance_mode', 'System')
        ctk.set_appearance_mode(appearance_mode)

        # Style treeviews for premium look
        style = ttk.Style()
        style.configure("Treeview", font=("Arial", 14), rowheight=30)
        style.configure("Treeview.Heading", font=("Arial", 16, "bold"))
        style.map("Treeview", background=[('selected', '#4682B4')], foreground=[('selected', '#FFFFFF')])

        # Menubar
        menubar = Menu(self.window)
        self.window.config(menu=menubar)
        file_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Logout", font=("Arial", 14), command=self.logout)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", font=("Arial", 14), command=self.window.quit)

        # Sidebar (Premium Design)
        self.sidebar = ctk.CTkFrame(self.window, width=250, fg_color="#2B2D42")
        self.sidebar.pack(side="left", fill="y")

        self.nav_buttons = {}
        sections = [
            ("dashboard", "Dashboard", self.show_dashboard),
            ("products", "Products", self.show_products),
            ("customers", "Customers", self.show_customers),
            ("sales", "Sales", self.show_sales),
            ("history", "Sales History", self.show_history)
        ]
        if role == 'admin':
            sections += [
                ("suppliers", "Suppliers", self.show_suppliers),
                ("expenses", "Expenses", self.show_expenses),
                ("purchase_orders", "Purchase Orders", self.show_purchase_orders),
                ("reports", "Reports", self.show_reports),
                ("users", "User Management", self.show_users),
                ("settings", "Settings", self.show_settings)
            ]

        for key, text, command in sections:
            try:
                icon = ctk.CTkImage(Image.open(f"icons/{key}.png"), size=(24, 24))
            except FileNotFoundError:
                icon = None
            button = ctk.CTkButton(self.sidebar, image=icon, text=text, compound="left",
                                   fg_color="transparent", hover_color="#EDF2F4",
                                   text_color="#EDF2F4", command=command, font=("Arial", 16, "bold"))
            button.pack(fill="x", padx=10, pady=5)
            self.nav_buttons[key] = button

        # Content frames
        self.content_frames = {}
        for section in [s[0] for s in sections]:
            self.content_frames[section] = ctk.CTkScrollableFrame(self.window)

        # Create sections
        self.create_dashboard()
        self.create_products()
        self.create_customers()
        self.create_sales()
        self.create_history()
        if role == 'admin':
            self.create_suppliers()
            self.create_expenses()
            self.create_purchase_orders()
            self.create_reports()
            self.create_users()
            self.create_settings()

        # Show dashboard by default
        self.current_frame = self.content_frames['dashboard']
        self.current_frame.pack(side="right", fill="both", expand=True)
        self.nav_buttons['dashboard'].configure(fg_color="#4682B4")

        # Status bar (Premium Design)
        status_bar = ctk.CTkFrame(self.window, height=30, fg_color="#2B2D42")
        status_bar.pack(side="bottom", fill="x")
        ctk.CTkLabel(status_bar, text=f"Logged in as: {self.username}", font=("Arial", 14, "bold"), text_color="#EDF2F4").pack(side="left", padx=10)
        self.date_label = ctk.CTkLabel(status_bar, text=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), font=("Arial", 14, "bold"), text_color="#EDF2F4")
        self.date_label.pack(side="right", padx=10)

        # Key bindings
        self.window.bind("<Control-1>", lambda event: self.show_dashboard())
        self.window.bind("<Control-2>", lambda event: self.show_products())
        self.window.bind("<Control-3>", lambda event: self.show_customers())
        self.window.bind("<Control-4>", lambda event: self.show_sales())
        self.window.bind("<Control-5>", lambda event: self.show_history())

        # Auto-refresh (increased interval to 5 seconds for performance)
        self.window.after(5000, self.refresh_realtime)
        self.update_time()

        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.window.mainloop()

    # Utility Methods
    def update_time(self):
        self.date_label.configure(text=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.window.after(1000, self.update_time)

    def reset_nav_buttons(self):
        for button in self.nav_buttons.values():
            button.configure(fg_color="transparent")

    def show_section(self, section):
        self.reset_nav_buttons()
        self.nav_buttons[section].configure(fg_color="#4682B4")
        self.current_frame.pack_forget()
        self.current_frame = self.content_frames[section]
        self.current_frame.pack(side="right", fill="both", expand=True)

    def show_dashboard(self): self.show_section('dashboard')
    def show_products(self): self.show_section('products')
    def show_customers(self): self.show_section('customers')
    def show_sales(self):
        self.load_customers_combobox()
        self.load_products_combobox()
        self.show_section('sales')
    def show_history(self): self.show_section('history')
    def show_suppliers(self): self.show_section('suppliers')
    def show_expenses(self): self.show_section('expenses')
    def show_purchase_orders(self): self.show_section('purchase_orders')
    def show_reports(self): self.show_section('reports')
    def show_users(self): self.show_section('users')
    def show_settings(self): self.show_section('settings')

    def logout(self):
        if messagebox.askyesno("Logout", "Are you sure you want to log out?"):
            self.window.destroy()
            LoginWindow()

    def on_closing(self):
        if messagebox.askyesno("Exit", "Are you sure you want to exit?"):
            conn.close()
            self.window.destroy()

    def refresh_realtime(self):
        self.update_dashboard()
        self.load_products()
        self.load_sales_history()
        self.load_purchase_orders()
        self.window.after(5000, self.refresh_realtime)

    def get_setting(self, key, default=''):
        cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
        result = cursor.fetchone()
        return result[0] if result else default

    def set_setting(self, key, value):
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()

    def get_logo_position(self):
        horizontal = self.get_setting('logo_horizontal', 'Left')
        vertical = self.get_setting('logo_vertical', 'Top')
        page_width = 210  # A4 width in mm
        logo_width = 30
        logo_height = 30
        x = {'Left': 10, 'Center': (page_width - logo_width) / 2, 'Right': page_width - logo_width - 10}.get(horizontal, 10)
        y = {'Top': 10, 'Middle': (297 - logo_height) / 2, 'Bottom': 297 - logo_height - 10}.get(vertical, 10)
        return x, y

    def send_email(self, subject, body):
        server = self.get_setting('email_server')
        port = int(self.get_setting('email_port', '587'))
        username = self.get_setting('email_username')
        password = self.get_setting('email_password')
        alert_email = self.get_setting('alert_email')

        if not all([server, port, username, password, alert_email]):
            print("Email settings are not configured")
            return

        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = username
        msg['To'] = alert_email

        try:
            with smtplib.SMTP(server, port) as s:
                s.starttls()
                s.login(username, password)
                s.sendmail(username, [alert_email], msg.as_string())
            print("Email sent successfully")
        except Exception as e:
            print(f"Failed to send email: {e}")

    def log_action(self, action, details):
        timestamp = datetime.datetime.now().isoformat()
        user = self.username
        cursor.execute("INSERT INTO audit_logs (timestamp, user, action, details) VALUES (?, ?, ?, ?)", (timestamp, user, action, details))
        conn.commit()

    # Dashboard Section
    def create_dashboard(self):
        frame = self.content_frames['dashboard']
        frame.configure(fg_color="#FFFFFF")

        stats_frame = ctk.CTkFrame(frame, fg_color="transparent")
        stats_frame.pack(pady=20, fill="x", padx=20)

        self.stats_labels = {
            'products': ctk.CTkLabel(stats_frame, text="Products: 0", font=("Arial", 16, "bold")),
            'customers': ctk.CTkLabel(stats_frame, text="Customers: 0", font=("Arial", 16, "bold")),
            'sales': ctk.CTkLabel(stats_frame, text="Sales: 0", font=("Arial", 16, "bold")),
            'revenue': ctk.CTkLabel(stats_frame, text="Revenue: $0.00", font=("Arial", 16, "bold")),
            'expenses': ctk.CTkLabel(stats_frame, text="Expenses: $0.00", font=("Arial", 16, "bold")),
            'best_seller': ctk.CTkLabel(stats_frame, text="Best Seller: N/A", font=("Arial", 16, "bold")),
            'sales_trend': ctk.CTkLabel(stats_frame, text="Sales Trend: N/A", font=("Arial", 16, "bold"))
        }

        for i, label in enumerate(self.stats_labels.values()):
            label.grid(row=i//4, column=i%4, padx=20, pady=10)

        self.alert_frame = ctk.CTkFrame(frame, fg_color="#FF9999")
        self.alert_tree = ttk.Treeview(self.alert_frame, columns=("Name", "Quantity"), show="headings")
        self.alert_tree.heading("Name", text="Product Name")
        self.alert_tree.heading("Quantity", text="Quantity")
        self.alert_tree.column("Name", width=200)
        self.alert_tree.column("Quantity", width=100)
        self.alert_tree.pack(padx=10, pady=5)

        self.update_dashboard()

    def update_dashboard(self):
        cursor.execute("SELECT COUNT(*) FROM products")
        products = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM customers")
        customers = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*), SUM(total) FROM sales")
        sales, revenue = cursor.fetchone()
        revenue = revenue or 0
        cursor.execute("SELECT SUM(amount) FROM expenses")
        expenses = cursor.fetchone()[0] or 0

        self.stats_labels['products'].configure(text=f"Products: {products}")
        self.stats_labels['customers'].configure(text=f"Customers: {customers}")
        self.stats_labels['sales'].configure(text=f"Sales: {sales}")
        self.stats_labels['revenue'].configure(text=f"Revenue: ${revenue:.2f}")
        self.stats_labels['expenses'].configure(text=f"Expenses: ${expenses:.2f}")

        cursor.execute("SELECT p.name, SUM(si.quantity) as total_sold FROM sale_items si JOIN products p ON si.product_id = p.id GROUP BY p.id ORDER BY total_sold DESC LIMIT 1")
        best_seller = cursor.fetchone()
        if best_seller:
            self.stats_labels['best_seller'].configure(text=f"Best Seller: {best_seller[0]} ({best_seller[1]} sold)")

        today = datetime.date.today()
        first_day_this_month = today.replace(day=1)
        last_month = first_day_this_month - datetime.timedelta(days=1)
        first_day_last_month = last_month.replace(day=1)

        cursor.execute("SELECT SUM(total) FROM sales WHERE date >= ? AND date < ?", (first_day_this_month.isoformat(), today.isoformat()))
        sales_this_month = cursor.fetchone()[0] or 0
        cursor.execute("SELECT SUM(total) FROM sales WHERE date >= ? AND date < ?", (first_day_last_month.isoformat(), first_day_this_month.isoformat()))
        sales_last_month = cursor.fetchone()[0] or 0

        trend = "N/A" if sales_last_month == 0 else f"{(sales_this_month - sales_last_month) / sales_last_month * 100:.2f}%"
        self.stats_labels['sales_trend'].configure(text=f"Sales Trend: {trend}")

        for item in self.alert_tree.get_children():
            self.alert_tree.delete(item)
        cursor.execute("SELECT name, quantity FROM products WHERE quantity < min_stock")
        low_stock = cursor.fetchall()
        if low_stock:
            for name, qty in low_stock:
                self.alert_tree.insert("", "end", values=(name, qty))
            self.alert_frame.pack(pady=20, padx=20, fill="x")
        else:
            self.alert_frame.pack_forget()

    # Products Section
    def create_products(self):
        frame = self.content_frames['products']
        frame.configure(fg_color="#FFFFFF")

        search_frame = ctk.CTkFrame(frame, fg_color="transparent")
        search_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(search_frame, text="Search:", font=("Arial", 16, "bold")).pack(side="left", padx=5)
        self.product_search = ctk.CTkEntry(search_frame, height=40, font=("Arial", 14))
        self.product_search.pack(side="left", fill="x", expand=True, padx=5)
        self.product_search.bind("<KeyRelease>", self.filter_products)

        form_frame = ctk.CTkFrame(frame, fg_color="transparent")
        form_frame.pack(pady=10, padx=20, fill="x")

        entries = [
            ("Name", "name", lambda m: ctk.CTkEntry(m, height=40, width=200, font=("Arial", 14))),
            ("Category", "category", lambda m: ctk.CTkComboBox(m, values=[
                "Laptop", "Monitor", "CPU", "GPU", "RAM", "Storage", "Motherboard",
                "Power Supply", "Case", "Keyboard", "Mouse", "Printer", "Accessories"
            ], height=40, width=200, font=("Arial", 14))),
            ("Quantity", "quantity", lambda m: ctk.CTkEntry(m, height=40, width=200, font=("Arial", 14))),
            ("Price", "price", lambda m: ctk.CTkEntry(m, height=40, width=200, font=("Arial", 14))),
            ("Min Stock", "min_stock", lambda m: ctk.CTkEntry(m, height=40, width=200, font=("Arial", 14))),
            ("Supplier", "supplier", lambda m: ctk.CTkComboBox(m, height=40, width=200, font=("Arial", 14))),
            ("Barcode", "barcode", lambda m: ctk.CTkEntry(m, height=40, width=200, font=("Arial", 14))),
            ("Discount (%)", "discount", lambda m: ctk.CTkEntry(m, height=40, width=200, font=("Arial", 14)))
        ]

        self.product_entries = {}
        for i, (label_text, key, widget_type) in enumerate(entries):
            ctk.CTkLabel(form_frame, text=label_text, font=("Arial", 14, "bold")).grid(row=0, column=i, padx=5, pady=5)
            entry = widget_type(form_frame)
            if key == 'supplier':
                self.load_suppliers_combobox(entry)
            entry.grid(row=1, column=i, padx=5, pady=5)
            self.product_entries[key] = entry

        ctk.CTkLabel(form_frame, text="Image:", font=("Arial", 14, "bold")).grid(row=2, column=0, padx=5, pady=5)
        self.product_image_label = ctk.CTkLabel(form_frame, text="No image", font=("Arial", 14))
        self.product_image_label.grid(row=2, column=1, columnspan=3, padx=5, pady=5)
        ctk.CTkButton(form_frame, text="Upload Image", command=self.upload_product_image, height=40, font=("Arial", 14)).grid(row=2, column=4, padx=5, pady=5)

        button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        button_frame.pack(pady=10)
        self.add_update_product_button = ctk.CTkButton(button_frame, text="Add Product", command=self.add_or_update_product, height=40, font=("Arial", 14))
        self.add_update_product_button.pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Delete Product", command=self.delete_product, fg_color="#d9534f", hover_color="#c9302c", height=40, font=("Arial", 14)).pack(side="left", padx=5)

        self.product_tree = ttk.Treeview(frame, columns=("ID", "Name", "Category", "Qty", "Price", "Min Stock", "Supplier", "Barcode", "Image", "Discount"), show="headings")
        for col in self.product_tree["columns"]:
            self.product_tree.heading(col, text=col)
            self.product_tree.column(col, width=100)
        self.product_tree.pack(fill="both", expand=True, padx=20, pady=10)
        self.product_tree.bind("<Double-1>", self.select_product)

        self.product_image_display = ctk.CTkLabel(frame, text="")
        self.product_image_display.pack(pady=10)

        self.load_products()
        self.selected_product_id = None

    def upload_product_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png *.gif")])
        if file_path:
            try:
                img = Image.open(file_path)
                filename = os.path.basename(file_path)
                dest_path = os.path.join("images", filename)
                if not os.path.exists("images"):
                    os.makedirs("images")
                img.save(dest_path)
                self.product_image_filename = filename
                self.product_image_label.configure(text=filename)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to upload image: {e}")

    def load_suppliers_combobox(self, combobox):
        cursor.execute("SELECT name FROM suppliers")
        suppliers = ["None"] + [row[0] for row in cursor.fetchall()]
        combobox.configure(values=suppliers)
        combobox.set("None")

    def load_products(self):
        for item in self.product_tree.get_children():
            self.product_tree.delete(item)
        cursor.execute("SELECT p.id, p.name, p.category, p.quantity, p.price, p.min_stock, s.name, p.barcode, p.image_path, p.discount FROM products p LEFT JOIN suppliers s ON p.supplier_id = s.id")
        for row in cursor.fetchall():
            self.product_tree.insert("", "end", values=row)

    def filter_products(self, event):
        search_term = self.product_search.get().lower()
        for item in self.product_tree.get_children():
            self.product_tree.delete(item)
        cursor.execute("SELECT p.id, p.name, p.category, p.quantity, p.price, p.min_stock, s.name, p.barcode, p.image_path, p.discount FROM products p LEFT JOIN suppliers s ON p.supplier_id = s.id WHERE LOWER(p.name) LIKE ? OR LOWER(p.barcode) LIKE ?", (f"%{search_term}%", f"%{search_term}%"))
        for row in cursor.fetchall():
            self.product_tree.insert("", "end", values=row)

    def select_product(self, event):
        selected = self.product_tree.selection()
        if selected:
            item = self.product_tree.item(selected[0])
            values = item['values']
            self.selected_product_id = values[0]
            self.product_entries['name'].delete(0, "end")
            self.product_entries['name'].insert(0, values[1])
            self.product_entries['category'].set(values[2])
            self.product_entries['quantity'].delete(0, "end")
            self.product_entries['quantity'].insert(0, values[3])
            self.product_entries['price'].delete(0, "end")
            self.product_entries['price'].insert(0, values[4])
            self.product_entries['min_stock'].delete(0, "end")
            self.product_entries['min_stock'].insert(0, values[5])
            supplier = values[6] if values[6] else "None"
            self.product_entries['supplier'].set(supplier)
            self.product_entries['barcode'].delete(0, "end")
            self.product_entries['barcode'].insert(0, values[7] if values[7] else "")
            self.product_image_filename = values[8]
            self.product_image_label.configure(text=values[8] if values[8] else "No image")
            self.product_entries['discount'].delete(0, "end")
            self.product_entries['discount'].insert(0, values[9] if len(values) > 9 else "0")
            self.add_update_product_button.configure(text="Update Product")

            if values[8] and os.path.exists(os.path.join("images", values[8])):
                try:
                    img = Image.open(os.path.join("images", values[8]))
                    img = img.resize((200, 200), Image.LANCZOS)
                    self.product_image = ctk.CTkImage(light_image=img, dark_image=img, size=(200, 200))
                    self.product_image_display.configure(image=self.product_image)
                    self.product_image_display.image = self.product_image
                except Exception as e:
                    print(f"Error loading image: {e}")
                    self.product_image_display.configure(image=None, text="Error loading image")
            else:
                self.product_image_display.configure(image=None, text="No image")

    def delete_product(self):
        selected = self.product_tree.selection()
        if selected:
            item = self.product_tree.item(selected[0])
            product_id = item['values'][0]
            if messagebox.askyesno("Confirm", "Are you sure you want to delete this product?"):
                cursor.execute("DELETE FROM products WHERE id=?", (product_id,))
                conn.commit()
                self.load_products()
                self.update_dashboard()
                self.log_action("Delete Product", f"Deleted product ID {product_id}")
                messagebox.showinfo("Success", "Product deleted")
        else:
            messagebox.showwarning("Warning", "Please select a product")

    def add_or_update_product(self):
        name = self.product_entries['name'].get().strip()
        category = self.product_entries['category'].get()
        quantity = self.product_entries['quantity'].get().strip()
        price = self.product_entries['price'].get().strip()
        min_stock = self.product_entries['min_stock'].get().strip()
        supplier_name = self.product_entries['supplier'].get()
        barcode = self.product_entries['barcode'].get().strip()
        discount = self.product_entries['discount'].get().strip() or "0"

        if not all([name, category, quantity, price, min_stock]):
            messagebox.showerror("Error", "All fields are required")
            return

        try:
            quantity = int(quantity)
            price = float(price)
            min_stock = int(min_stock)
            discount = float(discount)
            if quantity < 0 or price < 0 or min_stock < 0 or not 0 <= discount <= 100:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Invalid input values")
            return

        supplier_id = None
        if supplier_name != "None":
            cursor.execute("SELECT id FROM suppliers WHERE name=?", (supplier_name,))
            supplier = cursor.fetchone()
            if supplier:
                supplier_id = supplier[0]
            else:
                messagebox.showerror("Error", "Supplier not found")
                return

        if self.selected_product_id:
            cursor.execute("UPDATE products SET name=?, category=?, quantity=?, price=?, min_stock=?, supplier_id=?, barcode=?, image_path=?, discount=? WHERE id=?",
                           (name, category, quantity, price, min_stock, supplier_id, barcode, self.product_image_filename, discount, self.selected_product_id))
            conn.commit()
            self.sio.emit('inventory_updated', {'id': self.selected_product_id, 'quantity': quantity})
            self.load_products()
            self.update_dashboard()
            self.log_action("Update Product", f"Updated product ID {self.selected_product_id}")
            messagebox.showinfo("Success", "Product updated")
            self.clear_product_form()
        else:
            cursor.execute("INSERT INTO products (name, category, quantity, price, min_stock, supplier_id, barcode, image_path, discount) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (name, category, quantity, price, min_stock, supplier_id, barcode, self.product_image_filename, discount))
            conn.commit()
            self.load_products()
            self.update_dashboard()
            self.log_action("Add Product", f"Added new product: {name}")
            messagebox.showinfo("Success", "Product added")
            self.clear_product_form()

    def clear_product_form(self):
        self.product_entries['name'].delete(0, "end")
        self.product_entries['category'].set("Laptop")
        self.product_entries['quantity'].delete(0, "end")
        self.product_entries['price'].delete(0, "end")
        self.product_entries['min_stock'].delete(0, "end")
        self.product_entries['supplier'].set("None")
        self.product_entries['barcode'].delete(0, "end")
        self.product_entries['discount'].delete(0, "end")
        self.product_image_filename = None
        self.product_image_label.configure(text="No image")
        self.product_image_display.configure(image=None, text="")
        self.selected_product_id = None
        self.add_update_product_button.configure(text="Add Product")

    # Customers Section
    def create_customers(self):
        frame = self.content_frames['customers']
        frame.configure(fg_color="#FFFFFF")

        search_frame = ctk.CTkFrame(frame, fg_color="transparent")
        search_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(search_frame, text="Search:", font=("Arial", 16, "bold")).pack(side="left", padx=5)
        self.customer_search = ctk.CTkEntry(search_frame, height=40, font=("Arial", 14))
        self.customer_search.pack(side="left", fill="x", expand=True, padx=5)
        self.customer_search.bind("<KeyRelease>", self.filter_customers)

        form_frame = ctk.CTkFrame(frame, fg_color="transparent")
        form_frame.pack(pady=10, padx=20, fill="x")

        entries = [("Name", "name"), ("Phone", "phone"), ("Email", "email"), ("Points", "points")]
        self.customer_entries = {}
        for i, (label_text, key) in enumerate(entries):
            ctk.CTkLabel(form_frame, text=label_text, font=("Arial", 14, "bold")).grid(row=0, column=i, padx=5, pady=5)
            entry = ctk.CTkEntry(form_frame, height=40, width=250, font=("Arial", 14))
            entry.grid(row=1, column=i, padx=5, pady=5)
            self.customer_entries[key] = entry

        ctk.CTkLabel(form_frame, text="Notes:", font=("Arial", 14, "bold")).grid(row=2, column=0, padx=5, pady=5)
        self.customer_notes = ctk.CTkTextbox(form_frame, width=250, height=100, font=("Arial", 14))
        self.customer_notes.grid(row=2, column=1, columnspan=3, padx=5, pady=5)
        self.customer_entries['notes'] = self.customer_notes

        button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        button_frame.pack(pady=10)
        self.add_update_customer_button = ctk.CTkButton(button_frame, text="Add Customer", command=self.add_or_update_customer, height=40, font=("Arial", 14))
        self.add_update_customer_button.pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Delete Customer", command=self.delete_customer, fg_color="#d9534f", hover_color="#c9302c", height=40, font=("Arial", 14)).pack(side="left", padx=5)

        self.customer_tree = ttk.Treeview(frame, columns=("ID", "Name", "Phone", "Email", "Points", "Notes"), show="headings")
        for col in self.customer_tree["columns"]:
            self.customer_tree.heading(col, text=col)
            self.customer_tree.column(col, width=150)
        self.customer_tree.pack(fill="both", expand=True, padx=20, pady=10)
        self.customer_tree.bind("<Double-1>", self.select_customer)
        self.load_customers()

        ctk.CTkButton(frame, text="Generate Customer Report", command=self.generate_customer_report, height=40, font=("Arial", 14)).pack(pady=10)

        self.selected_customer_id = None

    def load_customers(self):
        for item in self.customer_tree.get_children():
            self.customer_tree.delete(item)
        cursor.execute("SELECT id, name, phone, email, loyalty_points, notes FROM customers")
        for row in cursor.fetchall():
            self.customer_tree.insert("", "end", values=row)

    def filter_customers(self, event):
        search_term = self.customer_search.get().lower()
        for item in self.customer_tree.get_children():
            self.customer_tree.delete(item)
        cursor.execute("SELECT id, name, phone, email, loyalty_points, notes FROM customers WHERE LOWER(name) LIKE ?", (f"%{search_term}%",))
        for row in cursor.fetchall():
            self.customer_tree.insert("", "end", values=row)

    def select_customer(self, event):
        selected = self.customer_tree.selection()
        if selected:
            item = self.customer_tree.item(selected[0])
            values = item['values']
            self.selected_customer_id = values[0]
            self.customer_entries['name'].delete(0, "end")
            self.customer_entries['name'].insert(0, values[1])
            self.customer_entries['phone'].delete(0, "end")
            self.customer_entries['phone'].insert(0, values[2])
            self.customer_entries['email'].delete(0, "end")
            self.customer_entries['email'].insert(0, values[3])
            self.customer_entries['points'].delete(0, "end")
            self.customer_entries['points'].insert(0, values[4])
            self.customer_notes.delete("1.0", "end")
            self.customer_notes.insert("1.0", values[5] if len(values) > 5 else "")
            self.add_update_customer_button.configure(text="Update Customer")

    def delete_customer(self):
        selected = self.customer_tree.selection()
        if selected:
            item = self.customer_tree.item(selected[0])
            customer_id = item['values'][0]
            if messagebox.askyesno("Confirm", "Are you sure you want to delete this customer?"):
                cursor.execute("DELETE FROM customers WHERE id=?", (customer_id,))
                conn.commit()
                self.load_customers()
                self.update_dashboard()
                self.log_action("Delete Customer", f"Deleted customer ID {customer_id}")
                messagebox.showinfo("Success", "Customer deleted")
        else:
            messagebox.showwarning("Warning", "Please select a customer")

    def add_or_update_customer(self):
        name = self.customer_entries['name'].get().strip()
        phone = self.customer_entries['phone'].get().strip()
        email = self.customer_entries['email'].get().strip()
        points = self.customer_entries['points'].get().strip() or "0"
        notes = self.customer_notes.get("1.0", "end-1c").strip()

        if not name:
            messagebox.showerror("Error", "Name is required")
            return

        try:
            points = int(points)
            if points < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Points must be a positive number")
            return

        if self.selected_customer_id:
            cursor.execute("UPDATE customers SET name=?, phone=?, email=?, loyalty_points=?, notes=? WHERE id=?",
                           (name, phone, email, points, notes, self.selected_customer_id))
            conn.commit()
            self.load_customers()
            self.update_dashboard()
            self.log_action("Update Customer", f"Updated customer ID {self.selected_customer_id}")
            messagebox.showinfo("Success", "Customer updated")
            self.clear_customer_form()
        else:
            cursor.execute("INSERT INTO customers (name, phone, email, loyalty_points, notes) VALUES (?, ?, ?, ?, ?)",
                           (name, phone, email, points, notes))
            conn.commit()
            self.load_customers()
            self.update_dashboard()
            self.log_action("Add Customer", f"Added new customer: {name}")
            messagebox.showinfo("Success", "Customer added")
            self.clear_customer_form()

    def clear_customer_form(self):
        for entry in self.customer_entries.values():
            if isinstance(entry, ctk.CTkEntry):
                entry.delete(0, "end")
            elif isinstance(entry, ctk.CTkTextbox):
                entry.delete("1.0", "end")
        self.selected_customer_id = None
        self.add_update_customer_button.configure(text="Add Customer")

    def generate_customer_report(self):
        selected = self.customer_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a customer")
            return
        item = self.customer_tree.item(selected[0])
        customer_id = item['values'][0]
        cursor.execute("SELECT name, phone, email, loyalty_points,notes FROM customers WHERE id=?", (customer_id,))
        customer = cursor.fetchone()
        if not customer:
            messagebox.showerror("Error", "Customer not found")
            return
        name, phone, email, points, notes= customer

        cursor.execute("SELECT s.id, s.date, s.total, s.discount FROM sales s WHERE s.customer_id=?", (customer_id,))
        sales = cursor.fetchall()

        pdf_file = self.generate_customer_report_pdf(customer_id, name, phone, email, points, sales, notes)
        if pdf_file:
            messagebox.showinfo("Success", f"Customer report generated: {pdf_file}")

    def generate_customer_report_pdf(self, customer_id, name, phone, email, points, sales, notes):
        shop_name = self.get_setting('shop_name', 'My Shop')
        shop_phone = self.get_setting('shop_phone', '')
        shop_email = self.get_setting('shop_email', '')
        shop_location = self.get_setting('shop_location','')
        greeting_message = self.get_setting('greeting_message', 'Thank you for your purchase!')
        shop_logo = self.get_setting('shop_logo')

        logo_x, logo_y = self.get_logo_position()
        text_start_y = logo_y + 35 if self.get_setting('logo_vertical', 'Top') == "Top" else 10

        align = {'Left': 'L', 'Center': 'C', 'Right': 'R'}.get(self.get_setting('shop_info_alignment', 'Center'), 'C')

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        if shop_logo and os.path.exists(os.path.join("images", shop_logo)):
            pdf.image(os.path.join("images", shop_logo), x=logo_x, y=logo_y, w=30)

        pdf.set_xy(10, text_start_y)
        pdf.cell(200, 10, txt=shop_name, ln=True, align=align)
        if shop_phone:
            pdf.cell(200, 10, txt=f"Phone: {shop_phone}", ln=True, align=align)
        if shop_email:
            pdf.cell(200, 10, txt=f"Email: {shop_email}", ln=True, align=align)
        #pdf.ln(10)
        if shop_location:
            pdf.cell(200, 10, txt=f"Shop Location : {shop_location}", ln=True, align=align)

        #pdf.cell(200, 10, txt="Customer Report", ln=True, align='C')
        pdf.ln(10)

        pdf.cell(200, 10, txt=f"Customer: {name}", ln=True)
        pdf.cell(200, 10, txt=f"Phone: {phone}", ln=True)
        pdf.cell(200, 10, txt=f"Email: {email}", ln=True)
       # pdf.cell(200, 10, txt=f"Loyalty Points: {points}", ln=True)
       # pdf.cell(200, 10, txt=f"Notes: {notes}", ln=True)
        pdf.ln(10)

        pdf.cell(200, 10, txt="Purchase History:", ln=True)
        if not sales:
            pdf.cell(200, 10, txt="No purchase history", ln=True)
        else:
            total_spent = 0
            for sale in sales:
                sale_id, date, total, discount = sale
                cursor.execute("SELECT p.name, si.quantity, si.price FROM sale_items si JOIN products p ON si.product_id = p.id WHERE si.sale_id=?", (sale_id,))
                items = cursor.fetchall()

                subtotal = sum(item[1] * item[2] for item in items)
                discount_amount = subtotal * (discount / 100) if discount > 0 else 0
                total_spent += total

                pdf.cell(200, 10, txt=f"Sale ID: {sale_id}   Date: {date}", ln=True)
                pdf.cell(80, 10, txt="Product Name", border=1)
                pdf.cell(30, 10, txt="Quantity", border=1)
                pdf.cell(30, 10, txt="Price", border=1)
                pdf.cell(50, 10, txt="Subtotal", border=1)
                pdf.ln()

                for item in items:
                    product, quantity, price = item
                    subtotal_item = quantity * price
                    pdf.cell(80, 10, txt=product, border=1)
                    pdf.cell(30, 10, txt=str(quantity), border=1)
                    pdf.cell(30, 10, txt=f"${price:.2f}", border=1)
                    pdf.cell(50, 10, txt=f"${subtotal_item:.2f}", border=1)
                    pdf.ln()

                pdf.cell(140, 10, txt="", ln=False)
                pdf.cell(50, 10, txt=f"Subtotal: ${subtotal:.2f}", ln=True)
                if discount > 0:
                    pdf.cell(140, 10, txt="", ln=False)
                    pdf.cell(50, 10, txt=f"Discount ({discount}%): -${discount_amount:.2f}", ln=True)
                pdf.cell(140, 10, txt="", ln=False)
                pdf.cell(50, 10, txt=f"Total: ${total:.2f}", ln=True)
                pdf.ln(10)

            pdf.ln(10)
            pdf.cell(140, 10, txt="", ln=False)
            pdf.cell(50, 10, txt=f"Total Spent: ${total_spent:.2f}", ln=True)

        pdf.ln(20)
        pdf.cell(200, 10, txt=greeting_message, ln=True, align='C')

        pdf_file = f"customer_report_{customer_id}.pdf"
        pdf.output(pdf_file)
        return pdf_file

    # Sales Section
    def create_sales(self):
        frame = self.content_frames['sales']
        frame.configure(fg_color="#FFFFFF")

        customer_frame = ctk.CTkFrame(frame, fg_color="transparent")
        customer_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(customer_frame, text="Customer:", font=("Arial", 16, "bold")).pack(side="left", padx=5)
        self.customer_combobox = ctk.CTkComboBox(customer_frame, width=250, height=40, font=("Arial", 14))
        self.load_customers_combobox()
        self.customer_combobox.pack(side="left", padx=5)

        add_frame = ctk.CTkFrame(frame, fg_color="transparent")
        add_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(add_frame, text="Product:", font=("Arial", 16, "bold")).pack(side="left", padx=5)
        self.product_combobox = ctk.CTkComboBox(add_frame, width=250, height=40, font=("Arial", 14))
        self.load_products_combobox()
        self.product_combobox.pack(side="left", padx=5)
        ctk.CTkButton(add_frame, text="Scan Barcode", command=self.scan_barcode, height=40, font=("Arial", 14)).pack(side="left", padx=5)
        ctk.CTkLabel(add_frame, text="Quantity:", font=("Arial", 16, "bold")).pack(side="left", padx=5)
        self.quantity_entry = ctk.CTkEntry(add_frame, width=100, height=40, font=("Arial", 14))
        self.quantity_entry.pack(side="left", padx=5)
        ctk.CTkButton(add_frame, text="Add to Sale", command=self.add_to_sale, height=40, font=("Arial", 14)).pack(side="left", padx=10)

        self.sale_tree = ttk.Treeview(frame, columns=("Product", "Quantity", "Price", "Subtotal"), show="headings")
        for col in self.sale_tree["columns"]:
            self.sale_tree.heading(col, text=col)
            self.sale_tree.column(col, width=150)
        self.sale_tree.pack(fill="both", expand=True, padx=20, pady=10)

        total_frame = ctk.CTkFrame(frame, fg_color="transparent")
        total_frame.pack(pady=10, padx=20, fill="x")
        self.subtotal_label = ctk.CTkLabel(total_frame, text="Subtotal: $0.00", font=("Arial", 16, "bold"))
        self.subtotal_label.pack(side="left", padx=10)
        ctk.CTkLabel(total_frame, text="Discount (%):", font=("Arial", 16, "bold")).pack(side="left", padx=5)
        self.discount_entry = ctk.CTkEntry(total_frame, width=100, height=40, font=("Arial", 14))
        self.discount_entry.pack(side="left", padx=5)
        ctk.CTkButton(total_frame, text="Apply", command=self.apply_discount, height=40, font=("Arial", 14)).pack(side="left", padx=5)
        self.total_label = ctk.CTkLabel(total_frame, text="Total: $0.00", font=("Arial", 16, "bold"))
        self.total_label.pack(side="left", padx=10)

        payment_frame = ctk.CTkFrame(frame, fg_color="transparent")
        payment_frame.pack(pady=10)
        ctk.CTkLabel(payment_frame, text="Payment Method:", font=("Arial", 16, "bold")).pack(side="left", padx=5)
        self.payment_method = ctk.CTkComboBox(payment_frame, values=["Cash", "Credit Card", "Mobile Payment", "Online"], width=150, height=40, font=("Arial", 14))
        self.payment_method.pack(side="left", padx=5)
        ctk.CTkButton(payment_frame, text="Finalize Sale", command=self.finalize_sale, height=40, font=("Arial", 14)).pack(side="left", padx=5)

        self.current_sale_items = []
        self.current_discount = 0.0

    def scan_barcode(self):
        top = ctk.CTkToplevel(self.window)
        top.title("Scan Barcode")
        top.geometry("640x480")
        label = ctk.CTkLabel(top)
        label.pack(fill="both", expand=True)
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            messagebox.showerror("Error", "Could not access camera")
            top.destroy()
            return

        def update_frame():
            ret, frame = cap.read()
            if ret:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                barcodes = decode(gray)
                for barcode in barcodes:
                    barcode_data = barcode.data.decode("utf-8")
                    cursor.execute("SELECT name FROM products WHERE barcode=?", (barcode_data,))
                    product = cursor.fetchone()
                    if product:
                        self.product_combobox.set(product[0])
                        cap.release()
                        top.destroy()
                        return
                    (x, y, w, h) = barcode.rect
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame)
                imgtk = ctk.CTkImage(light_image=img, dark_image=img, size=(640, 480))
                label.configure(image=imgtk)
                label.image = imgtk
                top.after(10, update_frame)
            else:
                messagebox.showerror("Error", "Failed to capture frame")
                cap.release()
                top.destroy()

        update_frame()
        top.protocol("WM_DELETE_WINDOW", lambda: (cap.release(), top.destroy()))

    def load_customers_combobox(self):
        cursor.execute("SELECT name FROM customers")
        customers = [row[0] for row in cursor.fetchall()]
        self.customer_combobox.configure(values=customers)
        if customers:
            self.customer_combobox.set(customers[0])

    def load_products_combobox(self):
        cursor.execute("SELECT name FROM products")
        products = [row[0] for row in cursor.fetchall()]
        self.product_combobox.configure(values=products)
        if products:
            self.product_combobox.set(products[0])

    def add_to_sale(self):
        product_name = self.product_combobox.get()
        quantity_str = self.quantity_entry.get().strip()

        if not product_name or not quantity_str:
            messagebox.showerror("Error", "Product and quantity are required")
            return

        try:
            quantity = int(quantity_str)
            if quantity <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Quantity must be a positive integer")
            return

        cursor.execute("SELECT id, name, quantity, price, discount FROM products WHERE name=?", (product_name,))
        product = cursor.fetchone()
        if not product:
            messagebox.showerror("Error", "Product not found")
            return

        product_id, name, available_qty, price, discount = product
        if quantity > available_qty:
            messagebox.showerror("Error", f"Insufficient stock. Available: {available_qty}")
            return

        discounted_price = price * (1 - discount / 100)
        subtotal_item = quantity * discounted_price
        self.sale_tree.insert("", "end", values=(name, quantity, f"${discounted_price:.2f}", f"${subtotal_item:.2f}"))

        self.current_sale_items.append({'id': product_id, 'name': name, 'quantity': quantity, 'price': discounted_price})
        self.quantity_entry.delete(0, "end")

        self.update_sale_totals()

    def apply_discount(self):
        discount_str = self.discount_entry.get().strip()
        try:
            discount = float(discount_str)
            if not 0 <= discount <= 100:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Discount must be between 0 and 100")
            return

        self.current_discount = discount
        self.update_sale_totals()

    def update_sale_totals(self):
        subtotal = sum(item['quantity'] * item['price'] for item in self.current_sale_items)
        self.subtotal_label.configure(text=f"Subtotal: ${subtotal:.2f}")
        total = subtotal * (1 - self.current_discount / 100)
        self.total_label.configure(text=f"Total: ${total:.2f}")

    def finalize_sale(self):
        payment_method = self.payment_method.get()
        if payment_method == "Cash":
            self.finalize_sale_cash()
        elif payment_method in ["Credit Card", "Mobile Payment", "Online"]:
            self.finalize_sale_online(payment_method)
        else:
            messagebox.showerror("Error", "Invalid payment method")

    def finalize_sale_cash(self):
        self.finalize_sale_common("Cash")

    def finalize_sale_online(self, payment_method):
        total = sum(item['quantity'] * item['price'] for item in self.current_sale_items) * (1 - self.current_discount / 100)
        try:
            # Simulate payment processing (replace with actual integration)
            messagebox.showinfo("Payment", f"Processing {payment_method} payment for ${total:.2f}")
            self.finalize_sale_common(payment_method)
        except Exception as e:
            messagebox.showerror("Error", f"Payment failed: {e}")

    def finalize_sale_common(self, payment_method):
        customer_name = self.customer_combobox.get()
        if not customer_name:
            messagebox.showerror("Error", "Please select a customer")
            return

        if not self.current_sale_items:
            messagebox.showerror("Error", "No items in the sale")
            return

        cursor.execute("SELECT id FROM customers WHERE name=?", (customer_name,))
        customer = cursor.fetchone()
        if not customer:
            messagebox.showerror("Error", "Customer not found")
            return
        customer_id = customer[0]

        subtotal = sum(item['quantity'] * item['price'] for item in self.current_sale_items)
        total = subtotal * (1 - self.current_discount / 100)

        date = datetime.date.today().isoformat()
        cursor.execute("INSERT INTO sales (customer_id, date, total, discount, payment_method) VALUES (?, ?, ?, ?, ?)",
                       (customer_id, date, total, self.current_discount, payment_method))
        sale_id = cursor.lastrowid

        for item in self.current_sale_items:
            cursor.execute("INSERT INTO sale_items (sale_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                           (sale_id, item['id'], item['quantity'], item['price']))
            cursor.execute("UPDATE products SET quantity = quantity - ? WHERE id = ?",
                           (item['quantity'], item['id']))
            self.sio.emit('inventory_updated', {'id': item['id'], 'quantity': item['quantity']})

        points_earned = int(total // 10)
        cursor.execute("UPDATE customers SET loyalty_points = loyalty_points + ? WHERE id = ?",
                       (points_earned, customer_id))

        conn.commit()

        self.sio.emit('new_sale', {'customer': customer_name, 'total': total, 'date': date})

        cursor.execute("SELECT name, quantity, min_stock FROM products WHERE quantity < min_stock")
        low_stock_products = cursor.fetchall()
        if low_stock_products:
            body = "The following products are low on stock:\n"
            for product in low_stock_products:
                body += f"- {product[0]}: {product[1]} (min: {product[2]})\n"
            self.send_email("Low Stock Alert", body)

        self.sale_tree.delete(*self.sale_tree.get_children())
        self.subtotal_label.configure(text="Subtotal: $0.00")
        self.total_label.configure(text="Total: $0.00")
        self.discount_entry.delete(0, "end")
        self.current_sale_items = []
        self.current_discount = 0.0
        self.update_dashboard()
        self.load_sales_history()
        self.log_action("Complete Sale", f"Completed sale ID {sale_id} via {payment_method}")
        messagebox.showinfo("Success", f"Sale completed via {payment_method}")

    # Sales History Section
    def create_history(self):
        frame = self.content_frames['history']
        frame.configure(fg_color="#FFFFFF")

        self.history_tree = ttk.Treeview(frame, columns=("ID", "Date", "Customer", "Total", "Payment Method"), show="headings")
        for col in self.history_tree["columns"]:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=150)
        self.history_tree.pack(fill="both", expand=True, padx=20, pady=10)
        self.history_tree.bind("<<TreeviewSelect>>", self.update_sale_items)

        self.sale_items_tree = ttk.Treeview(frame, columns=("Product", "Quantity", "Price", "Subtotal"), show="headings")
        for col in self.sale_items_tree["columns"]:
            self.sale_items_tree.heading(col, text=col)
            self.sale_items_tree.column(col, width=150)
        self.sale_items_tree.pack(fill="both", expand=True, padx=20, pady=10)

        button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        button_frame.pack(pady=10)
        ctk.CTkButton(button_frame, text="Generate Receipt", command=self.generate_receipt, height=40, font=("Arial", 14)).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Print Receipt", command=self.print_receipt, height=40, font=("Arial", 14)).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Process Return", command=self.process_return, height=40, font=("Arial", 14)).pack(side="left", padx=5)

        self.load_sales_history()

    def load_sales_history(self):
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        cursor.execute("SELECT s.id, s.date, c.name, s.total, s.payment_method FROM sales s JOIN customers c ON s.customer_id = c.id")
        for row in cursor.fetchall():
            self.history_tree.insert("", "end", values=(row[0], row[1], row[2], f"${row[3]:.2f}", row[4]))

    def update_sale_items(self, event):
        selected = self.history_tree.selection()
        if selected:
            item = self.history_tree.item(selected[0])
            sale_id = item['values'][0]
            for i in self.sale_items_tree.get_children():
                self.sale_items_tree.delete(i)
            cursor.execute("SELECT p.name, si.quantity, si.price, si.quantity * si.price FROM sale_items si JOIN products p ON si.product_id = p.id WHERE si.sale_id=?", (sale_id,))
            for row in cursor.fetchall():
                self.sale_items_tree.insert("", "end", values=row)

    def generate_receipt(self):
        selected = self.history_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a sale")
            return
        item = self.history_tree.item(selected[0])
        sale_id = item['values'][0]
        pdf_file = self.generate_receipt_pdf(sale_id)
        if pdf_file:
            messagebox.showinfo("Success", f"Receipt generated: {pdf_file}")

    def print_receipt(self):
        selected = self.history_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a sale")
            return
        item = self.history_tree.item(selected[0])
        sale_id = item['values'][0]
        pdf_file = self.generate_receipt_pdf(sale_id)
        if pdf_file:
            try:
                if os.name == 'nt':
                    os.startfile(pdf_file, "print")
                else:
                    subprocess.run(["lpr", pdf_file])
                messagebox.showinfo("Success", "Receipt sent to printer")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to print: {e}")

    def generate_receipt_pdf(self, sale_id):
        cursor.execute("SELECT s.date, c.name, s.total, s.discount, s.payment_method FROM sales s JOIN customers c ON s.customer_id = c.id WHERE s.id=?", (sale_id,))
        sale = cursor.fetchone()
        if not sale:
            return None
        date, customer_name, total, discount, payment_method = sale

        cursor.execute("SELECT p.name, si.quantity, si.price FROM sale_items si JOIN products p ON si.product_id = p.id WHERE si.sale_id=?", (sale_id,))
        items = cursor.fetchall()

        shop_name = self.get_setting('shop_name', 'My Shop')
        shop_phone = self.get_setting('shop_phone', '')
        shop_email = self.get_setting('shop_email', '')
        shop_location = self.get_setting('shop_location', '')
        greeting_message = self.get_setting('greeting_message', 'Thank you for your purchase!')
        shop_logo = self.get_setting('shop_logo')

        logo_x, logo_y = self.get_logo_position()
        text_start_y = logo_y + 35 if self.get_setting('logo_vertical', 'Top') == "Top" else 10

        align = {'Left': 'L', 'Center': 'C', 'Right': 'R'}.get(self.get_setting('shop_info_alignment', 'Center'), 'C')

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        if shop_logo and os.path.exists(os.path.join("images", shop_logo)):
            pdf.image(os.path.join("images", shop_logo), x=logo_x, y=logo_y, w=30)

        pdf.set_xy(10, text_start_y)
        pdf.cell(200, 10, txt=shop_name, ln=True, align=align)
        if shop_phone:
            pdf.cell(200, 10, txt=f"Phone: {shop_phone}", ln=True, align=align)
        if shop_email:
            pdf.cell(200, 10, txt=f"Email: {shop_email}", ln=True, align=align)
        
        pdf.cell(200, 10, txt=f"Shop Location: {shop_location}", ln=True, align=align)
        pdf.ln(10)

        pdf.cell(200, 10, txt=f"Sale ID: {sale_id}", ln=True)
        pdf.cell(200, 10, txt=f"Date: {date}", ln=True)
        pdf.cell(200, 10, txt=f"Customer: {customer_name}", ln=True)
        pdf.cell(200, 10, txt=f"Payment Method: {payment_method}", ln=True)
        pdf.ln(10)

        pdf.cell(80, 10, txt="Product", border=1)
        pdf.cell(30, 10, txt="Quantity", border=1)
        pdf.cell(30, 10, txt="Price", border=1)
        pdf.cell(50, 10, txt="Subtotal", border=1)
        pdf.ln()

        for item in items:
            product, quantity, price = item
            subtotal = quantity * price
            pdf.cell(80, 10, txt=product, border=1)
            pdf.cell(30, 10, txt=str(quantity), border=1)
            pdf.cell(30, 10, txt=f"${price:.2f}", border=1)
            pdf.cell(50, 10, txt=f"${subtotal:.2f}", border=1)
            pdf.ln()

        pdf.ln(10)
        pdf.cell(140, 10, txt="Subtotal", border=1)
        subtotal = sum(item[1] * item[2] for item in items)
        pdf.cell(50, 10, txt=f"${subtotal:.2f}", border=1)
        pdf.ln()

        if discount > 0:
            pdf.cell(140, 10, txt=f"Discount ({discount}%)", border=1)
            discount_amount = subtotal * (discount / 100)
            pdf.cell(50, 10, txt=f"-${discount_amount:.2f}", border=1)
            pdf.ln()

        pdf.cell(140, 10, txt="Total", border=1)
        pdf.cell(50, 10, txt=f"${total:.2f}", border=1)
        pdf.ln(20)

        pdf.cell(200, 10, txt=greeting_message, ln=True, align='C')

        pdf_file = f"receipt_{sale_id}.pdf"
        pdf.output(pdf_file)
        return pdf_file

    def process_return(self):
        selected = self.history_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a sale")
            return
        item = self.history_tree.item(selected[0])
        sale_id = item['values'][0]

        cursor.execute("SELECT si.id, p.name, si.quantity, si.price FROM sale_items si JOIN products p ON si.product_id = p.id WHERE si.sale_id=?", (sale_id,))
        sale_items = cursor.fetchall()

        return_window = ctk.CTkToplevel(self.window)
        return_window.title("Process Return")
        return_window.geometry("600x400")

        tree = ttk.Treeview(return_window, columns=("ID", "Product", "Quantity", "Price", "Return Qty"), show="headings")
        for col in tree["columns"]:
            tree.heading(col, text=col)
            tree.column(col, width=100)
        tree.pack(fill="both", expand=True)

        return_quantities = {}
        for item in sale_items:
            item_id, product, quantity, price = item
            tree.insert("", "end", values=(item_id, product, quantity, f"${price:.2f}", 0))
            return_quantities[item_id] = ctk.IntVar(value=0)

        def update_return_qty(event):
            selected = tree.selection()
            if selected:
                item_id = tree.item(selected[0])['values'][0]
                max_qty = next(item[2] for item in sale_items if item[0] == item_id)
                qty = simpledialog.askinteger("Return Quantity", "Enter quantity to return:", minvalue=0, maxvalue=max_qty)
                if qty is not None:
                    tree.set(selected[0], "Return Qty", qty)
                    return_quantities[item_id].set(qty)

        tree.bind("<Double-1>", update_return_qty)

        def confirm_return():
            total_return = 0
            for item_id, var in return_quantities.items():
                qty = var.get()
                if qty > 0:
                    cursor.execute("SELECT quantity, price FROM sale_items WHERE id=?", (item_id,))
                    sale_qty, price = cursor.fetchone()
                    if qty > sale_qty:
                        messagebox.showerror("Error", f"Cannot return more than sold for item ID {item_id}")
                        return
                    total_return += qty * price
                    cursor.execute("UPDATE products SET quantity = quantity + ? WHERE id = (SELECT product_id FROM sale_items WHERE id=?)", (qty, item_id))
                    self.log_action("Return Item", f"Returned {qty} of item ID {item_id} from sale ID {sale_id}")

            if total_return > 0:
                cursor.execute("UPDATE sales SET total = total - ? WHERE id=?", (total_return, sale_id))
                conn.commit()
                messagebox.showinfo("Success", f"Return processed. Total refunded: ${total_return:.2f}")
                self.load_sales_history()
                self.update_dashboard()
                return_window.destroy()
            else:
                messagebox.showwarning("Warning", "No items to return")

        ctk.CTkButton(return_window, text="Confirm Return", command=confirm_return, height=40, font=("Arial", 14)).pack(pady=10)

    # Suppliers Section
    def create_suppliers(self):
        frame = self.content_frames['suppliers']
        frame.configure(fg_color="#FFFFFF")

        form_frame = ctk.CTkFrame(frame, fg_color="transparent")
        form_frame.pack(pady=10, padx=20, fill="x")

        entries = [("Name", "name"), ("Contact", "contact"), ("Email", "email"), ("Products", "products")]
        self.supplier_entries = {}
        for i, (label_text, key) in enumerate(entries):
            ctk.CTkLabel(form_frame, text=label_text, font=("Arial", 14, "bold")).grid(row=0, column=i, padx=5, pady=5)
            entry = ctk.CTkEntry(form_frame, height=40, width=250, font=("Arial", 14))
            entry.grid(row=1, column=i, padx=5, pady=5)
            self.supplier_entries[key] = entry

        button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        button_frame.pack(pady=10)
        self.add_update_supplier_button = ctk.CTkButton(button_frame, text="Add Supplier", command=self.add_or_update_supplier, height=40, font=("Arial", 14))
        self.add_update_supplier_button.pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Delete Supplier", command=self.delete_supplier, fg_color="#d9534f", hover_color="#c9302c", height=40, font=("Arial", 14)).pack(side="left", padx=5)

        self.supplier_tree = ttk.Treeview(frame, columns=("ID", "Name", "Contact", "Email", "Products"), show="headings")
        for col in self.supplier_tree["columns"]:
            self.supplier_tree.heading(col, text=col)
            self.supplier_tree.column(col, width=150)
        self.supplier_tree.pack(fill="both", expand=True, padx=20, pady=10)
        self.supplier_tree.bind("<Double-1>", self.select_supplier)
        self.load_suppliers()

        self.selected_supplier_id = None

    def load_suppliers(self):
        for item in self.supplier_tree.get_children():
            self.supplier_tree.delete(item)
        cursor.execute("SELECT id, name, contact, email, products FROM suppliers")
        for row in cursor.fetchall():
            self.supplier_tree.insert("", "end", values=row)

    def select_supplier(self, event):
        selected = self.supplier_tree.selection()
        if selected:
            item = self.supplier_tree.item(selected[0])
            values = item['values']
            self.selected_supplier_id = values[0]
            self.supplier_entries['name'].delete(0, "end")
            self.supplier_entries['name'].insert(0, values[1])
            self.supplier_entries['contact'].delete(0, "end")
            self.supplier_entries['contact'].insert(0, values[2])
            self.supplier_entries['email'].delete(0, "end")
            self.supplier_entries['email'].insert(0, values[3])
            self.supplier_entries['products'].delete(0, "end")
            self.supplier_entries['products'].insert(0, values[4])
            self.add_update_supplier_button.configure(text="Update Supplier")

    def delete_supplier(self):
        selected = self.supplier_tree.selection()
        if selected:
            item = self.supplier_tree.item(selected[0])
            supplier_id = item['values'][0]
            if messagebox.askyesno("Confirm", "Are you sure you want to delete this supplier?"):
                cursor.execute("DELETE FROM suppliers WHERE id=?", (supplier_id,))
                conn.commit()
                self.load_suppliers()
                messagebox.showinfo("Success", "Supplier deleted")
        else:
            messagebox.showwarning("Warning", "Please select a supplier")

    def add_or_update_supplier(self):
        name = self.supplier_entries['name'].get().strip()
        contact = self.supplier_entries['contact'].get().strip()
        email = self.supplier_entries['email'].get().strip()
        products = self.supplier_entries['products'].get().strip()

        if not name:
            messagebox.showerror("Error", "Name is required")
            return

        if self.selected_supplier_id:
            cursor.execute("UPDATE suppliers SET name=?, contact=?, email=?, products=? WHERE id=?",
                           (name, contact, email, products, self.selected_supplier_id))
            conn.commit()
            self.load_suppliers()
            self.load_suppliers_combobox(self.product_entries['supplier'])
            messagebox.showinfo("Success", "Supplier updated")
            self.clear_supplier_form()
        else:
            cursor.execute("INSERT INTO suppliers (name, contact, email, products) VALUES (?, ?, ?, ?)",
                           (name, contact, email, products))
            conn.commit()
            self.load_suppliers()
            self.load_suppliers_combobox(self.product_entries['supplier'])
            messagebox.showinfo("Success", "Supplier added")
            self.clear_supplier_form()

    def clear_supplier_form(self):
        for entry in self.supplier_entries.values():
            entry.delete(0, "end")
        self.selected_supplier_id = None
        self.add_update_supplier_button.configure(text="Add Supplier")

    # Expenses Section
    def create_expenses(self):
        frame = self.content_frames['expenses']
        frame.configure(fg_color="#FFFFFF")

        form_frame = ctk.CTkFrame(frame, fg_color="transparent")
        form_frame.pack(pady=10, padx=20, fill="x")

        entries = [("Date", "date"), ("Category", "category"), ("Amount", "amount"), ("Description", "description")]
        self.expense_entries = {}
        for i, (label_text, key) in enumerate(entries):
            ctk.CTkLabel(form_frame, text=label_text, font=("Arial", 14, "bold")).grid(row=0, column=i, padx=5, pady=5)
            entry = ctk.CTkEntry(form_frame, width=200, height=40, placeholder_text="YYYY-MM-DD" if key == 'date' else "", font=("Arial", 14))
            entry.grid(row=1, column=i, padx=5, pady=5)
            self.expense_entries[key] = entry

        ctk.CTkButton(form_frame, text="Add Expense", command=self.add_expense, height=40, font=("Arial", 14)).grid(row=1, column=len(entries), padx=10, pady=5)

        self.expense_tree = ttk.Treeview(frame, columns=("ID", "Date", "Category", "Amount", "Description"), show="headings")
        for col in self.expense_tree["columns"]:
            self.expense_tree.heading(col, text=col)
            self.expense_tree.column(col, width=150)
        self.expense_tree.pack(fill="both", expand=True, padx=20, pady=10)
        self.load_expenses()

    def load_expenses(self):
        for item in self.expense_tree.get_children():
            self.expense_tree.delete(item)
        cursor.execute("SELECT id, date, category, amount, description FROM expenses")
        for row in cursor.fetchall():
            self.expense_tree.insert("", "end", values=(row[0], row[1], row[2], f"${row[3]:.2f}", row[4]))

    def add_expense(self):
        date = self.expense_entries['date'].get().strip()
        category = self.expense_entries['category'].get().strip()
        amount = self.expense_entries['amount'].get().strip()
        description = self.expense_entries['description'].get().strip()

        if not all([date, category, amount]):
            messagebox.showerror("Error", "Date, category, and amount are required")
            return

        try:
            datetime.datetime.strptime(date, "%Y-%m-%d")
            amount = float(amount)
            if amount < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Invalid date or amount")
            return

        cursor.execute("INSERT INTO expenses (date, category, amount, description) VALUES (?, ?, ?, ?)", (date, category, amount, description))
        conn.commit()
        self.load_expenses()
        self.update_dashboard()
        messagebox.showinfo("Success", "Expense added")

    # Purchase Orders Section
    def create_purchase_orders(self):
        frame = self.content_frames['purchase_orders']
        frame.configure(fg_color="#FFFFFF")

        form_frame = ctk.CTkFrame(frame, fg_color="transparent")
        form_frame.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(form_frame, text="Supplier:", font=("Arial", 14, "bold")).grid(row=0, column=0, padx=5, pady=5)
        self.po_supplier = ctk.CTkComboBox(form_frame, width=200, height=40, font=("Arial", 14))
        self.load_suppliers_combobox(self.po_supplier)
        self.po_supplier.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(form_frame, text="Product:", font=("Arial", 14, "bold")).grid(row=1, column=0, padx=5, pady=5)
        self.po_product = ctk.CTkComboBox(form_frame, width=200, height=40, font=("Arial", 14))
        self.load_products_combobox_po()
        self.po_product.grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkLabel(form_frame, text="Quantity:", font=("Arial", 14, "bold")).grid(row=2, column=0, padx=5, pady=5)
        self.po_quantity = ctk.CTkEntry(form_frame, width=200, height=40, font=("Arial", 14))
        self.po_quantity.grid(row=2, column=1, padx=5, pady=5)

        ctk.CTkButton(form_frame, text="Add to Order", command=self.add_to_po, height=40, font=("Arial", 14)).grid(row=3, column=0, columnspan=2, pady=5)

        self.po_items_tree = ttk.Treeview(frame, columns=("Product", "Quantity"), show="headings")
        self.po_items_tree.heading("Product", text="Product")
        self.po_items_tree.heading("Quantity", text="Quantity")
        self.po_items_tree.column("Product", width=200)
        self.po_items_tree.column("Quantity", width=100)
        self.po_items_tree.pack(fill="x", padx=20, pady=10)

        button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        button_frame.pack(pady=10)
        ctk.CTkButton(button_frame, text="Create Purchase Order", command=self.create_po, height=40, font=("Arial", 14)).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Auto Generate POs", command=self.auto_generate_pos, height=40, font=("Arial", 14)).pack(side="left", padx=5)

        self.po_tree = ttk.Treeview(frame, columns=("ID", "Supplier", "Date", "Status"), show="headings")
        for col in self.po_tree["columns"]:
            self.po_tree.heading(col, text=col)
            self.po_tree.column(col, width=150)
        self.po_tree.pack(fill="both", expand=True, padx=20, pady=10)

        status_frame = ctk.CTkFrame(frame, fg_color="transparent")
        status_frame.pack(pady=10)
        ctk.CTkButton(status_frame, text="Mark as Completed", command=self.mark_po_completed, height=40, font=("Arial", 14)).pack(side="left", padx=5)
        ctk.CTkButton(status_frame, text="Mark as Cancelled", command=self.mark_po_cancelled, height=40, font=("Arial", 14)).pack(side="left", padx=5)

        self.load_purchase_orders()
        self.current_po_items = []

    def load_products_combobox_po(self):
        cursor.execute("SELECT name FROM products")
        products = [row[0] for row in cursor.fetchall()]
        self.po_product.configure(values=products)
        if products:
            self.po_product.set(products[0])

    def add_to_po(self):
        product_name = self.po_product.get()
        quantity_str = self.po_quantity.get().strip()

        if not product_name or not quantity_str:
            messagebox.showerror("Error", "Product and quantity are required")
            return
        try:
            quantity = int(quantity_str)
            if quantity <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Quantity must be a positive integer")
            return

        cursor.execute("SELECT id, name FROM products WHERE name=?", (product_name,))
        product = cursor.fetchone()
        if not product:
            messagebox.showerror("Error", "Product not found")
            return

        product_id, name = product
        self.po_items_tree.insert("", "end", values=(name, quantity))
        self.current_po_items.append({'id': product_id, 'name': name, 'quantity': quantity})
        self.po_quantity.delete(0, "end")

    def create_po(self):
        supplier_name = self.po_supplier.get()
        if not supplier_name or supplier_name == "None":
            messagebox.showerror("Error", "Select a supplier")
            return

        if not self.current_po_items:
            messagebox.showerror("Error", "No items in order")
            return

        cursor.execute("SELECT id FROM suppliers WHERE name=?", (supplier_name,))
        supplier = cursor.fetchone()
        if not supplier:
            messagebox.showerror("Error", "Supplier not found")
            return
        supplier_id = supplier[0]

        date = datetime.date.today().isoformat()
        cursor.execute("INSERT INTO purchase_orders (supplier_id, date, status) VALUES (?, ?, ?)", (supplier_id, date, "Pending"))
        po_id = cursor.lastrowid

        for item in self.current_po_items:
            cursor.execute("INSERT INTO purchase_order_items (po_id, product_id, quantity) VALUES (?, ?, ?)", (po_id, item['id'], item['quantity']))

        conn.commit()
        self.sio.emit('new_purchase_order', {'po_id': po_id, 'supplier': supplier_name, 'date': date, 'status': 'Pending'})
        self.po_items_tree.delete(*self.po_items_tree.get_children())
        self.current_po_items = []
        self.load_purchase_orders()
        messagebox.showinfo("Success", "Purchase order created")

    def auto_generate_pos(self):
        cursor.execute("SELECT p.id, p.name, p.quantity, p.min_stock, p.supplier_id FROM products p WHERE p.quantity < p.min_stock AND p.supplier_id IS NOT NULL")
        low_stock_products = cursor.fetchall()
        if not low_stock_products:
            messagebox.showinfo("Info", "No low stock products to reorder")
            return

        suppliers = {}
        for product in low_stock_products:
            product_id, name, quantity, min_stock, supplier_id = product
            reorder_qty = min_stock - quantity + 10
            if supplier_id not in suppliers:
                suppliers[supplier_id] = []
            suppliers[supplier_id].append({'id': product_id, 'name': name, 'quantity': reorder_qty})

        for supplier_id, items in suppliers.items():
            date = datetime.date.today().isoformat()
            cursor.execute("INSERT INTO purchase_orders (supplier_id, date, status) VALUES (?, ?, ?)", (supplier_id, date, "Pending"))
            po_id = cursor.lastrowid
            for item in items:
                cursor.execute("INSERT INTO purchase_order_items (po_id, product_id, quantity) VALUES (?, ?, ?)", (po_id, item['id'], item['quantity']))
            conn.commit()
            cursor.execute("SELECT name FROM suppliers WHERE id=?", (supplier_id,))
            supplier_name = cursor.fetchone()[0]
            self.sio.emit('new_purchase_order', {'po_id': po_id, 'supplier': supplier_name, 'date': date, 'status': 'Pending'})

        self.load_purchase_orders()
        messagebox.showinfo("Success", "Purchase orders generated for low stock products")

    def load_purchase_orders(self):
        for item in self.po_tree.get_children():
            self.po_tree.delete(item)
        cursor.execute("SELECT po.id, s.name, po.date, po.status FROM purchase_orders po JOIN suppliers s ON po.supplier_id = s.id")
        for row in cursor.fetchall():
            self.po_tree.insert("", "end", values=row)

    def mark_po_completed(self):
        selected = self.po_tree.selection()
        if selected:
            item = self.po_tree.item(selected[0])
            po_id = item['values'][0]
            cursor.execute("UPDATE purchase_orders SET status='Completed' WHERE id=?", (po_id,))
            conn.commit()
            self.load_purchase_orders()
            self.sio.emit('purchase_order_updated', {'po_id': po_id, 'status': 'Completed'})
            messagebox.showinfo("Success", "Purchase order marked as completed")
        else:
            messagebox.showwarning("Warning", "Please select a purchase order")

    def mark_po_cancelled(self):
        selected = self.po_tree.selection()
        if selected:
            item = self.po_tree.item(selected[0])
            po_id = item['values'][0]
            cursor.execute("UPDATE purchase_orders SET status='Cancelled' WHERE id=?", (po_id,))
            conn.commit()
            self.load_purchase_orders()
            self.sio.emit('purchase_order_updated', {'po_id': po_id, 'status': 'Cancelled'})
            messagebox.showinfo("Success", "Purchase order marked as cancelled")
        else:
            messagebox.showwarning("Warning", "Please select a purchase order")

    # Reports Section
    def create_reports(self):
        frame = self.content_frames['reports']
        frame.configure(fg_color="#FFFFFF")

        date_frame = ctk.CTkFrame(frame, fg_color="transparent")
        date_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(date_frame, text="From:", font=("Arial", 14, "bold")).pack(side="left", padx=5)
        self.start_date = ctk.CTkEntry(date_frame, placeholder_text="YYYY-MM-DD", width=150, height=40, font=("Arial", 14))
        self.start_date.pack(side="left", padx=5)
        ctk.CTkLabel(date_frame, text="To:", font=("Arial", 14, "bold")).pack(side="left", padx=5)
        self.end_date = ctk.CTkEntry(date_frame, placeholder_text="YYYY-MM-DD", width=150, height=40, font=("Arial", 14))
        self.end_date.pack(side="left", padx=5)
        ctk.CTkButton(date_frame, text="Generate", command=self.generate_report, height=40, font=("Arial", 14)).pack(side="left", padx=10)

        self.report_tree = ttk.Treeview(frame, columns=("Period", "Total Sales", "Total Expenses", "Profit"), show="headings")
        for col in self.report_tree["columns"]:
            self.report_tree.heading(col, text=col)
            self.report_tree.column(col, width=150)
        self.report_tree.pack(fill="both", expand=True, padx=20, pady=10)

        chart_frame = ctk.CTkFrame(frame, fg_color="transparent")
        chart_frame.pack(pady=10, fill="both", expand=True)
        self.fig, self.ax = plt.subplots(figsize=(8, 4))
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        report_button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        report_button_frame.pack(pady=10)
        ctk.CTkButton(report_button_frame, text="Sales by Category", command=self.generate_sales_by_category, height=40, font=("Arial", 14)).pack(side="left", padx=5)
        ctk.CTkButton(report_button_frame, text="Top Customers", command=self.generate_top_customers, height=40, font=("Arial", 14)).pack(side="left", padx=5)

    def generate_report(self):
        start = self.start_date.get().strip()
        end = self.end_date.get().strip()

        try:
            datetime.datetime.strptime(start, "%Y-%m-%d")
            datetime.datetime.strptime(end, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Error", "Dates must be in YYYY-MM-DD format")
            return

        cursor.execute("SELECT SUM(total) FROM sales WHERE date BETWEEN ? AND ?", (start, end))
        total_sales = cursor.fetchone()[0] or 0
        cursor.execute("SELECT SUM(amount) FROM expenses WHERE date BETWEEN ? AND ?", (start, end))
        total_expenses = cursor.fetchone()[0] or 0
        profit = total_sales - total_expenses

        for item in self.report_tree.get_children():
            self.report_tree.delete(item)
        self.report_tree.insert("", "end", values=(f"{start} to {end}", f"${total_sales:.2f}", f"${total_expenses:.2f}", f"${profit:.2f}"))

        cursor.execute("SELECT strftime('%Y-%m', date) AS month, SUM(total) FROM sales WHERE date BETWEEN ? AND ? GROUP BY month", (start, end))
        monthly_sales = cursor.fetchall()
        self.ax.clear()
        if monthly_sales:
            months = [row[0] for row in monthly_sales]
            sales = [row[1] for row in monthly_sales]
            self.ax.bar(months, sales, color='#4682B4')
            self.ax.set_title("Monthly Sales")
            self.ax.set_xlabel("Month")
            self.ax.set_ylabel("Total Sales ($)")
            self.canvas.draw()
        else:
            self.ax.text(0.5, 0.5, "No sales data for this period", horizontalalignment='center', verticalalignment='center')
            self.canvas.draw()

    def generate_sales_by_category(self):
        start = self.start_date.get().strip()
        end = self.end_date.get().strip()
        try:
            datetime.datetime.strptime(start, "%Y-%m-%d")
            datetime.datetime.strptime(end, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Error", "Dates must be in YYYY-MM-DD format")
            return

        cursor.execute("""
            SELECT p.category, SUM(si.quantity * si.price) as total
            FROM sale_items si
            JOIN products p ON si.product_id = p.id
            JOIN sales s ON si.sale_id = s.id
            WHERE s.date BETWEEN ? AND ?
            GROUP BY p.category
        """, (start, end))
        data = cursor.fetchall()

        report_window = ctk.CTkToplevel(self.window)
        report_window.title("Sales by Category")
        report_window.geometry("400x300")

        tree = ttk.Treeview(report_window, columns=("Category", "Total Sales"), show="headings")
        tree.heading("Category", text="Category")
        tree.heading("Total Sales", text="Total Sales")
        tree.column("Category", width=150)
        tree.column("Total Sales", width=150)
        for row in data:
            tree.insert("", "end", values=(row[0], f"${row[1]:.2f}"))
        tree.pack(fill="both", expand=True)

    def generate_top_customers(self):
        start = self.start_date.get().strip()
        end = self.end_date.get().strip()
        try:
            datetime.datetime.strptime(start, "%Y-%m-%d")
            datetime.datetime.strptime(end, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Error", "Dates must be in YYYY-MM-DD format")
            return

        cursor.execute("""
            SELECT c.name, SUM(s.total) as total_spent
            FROM sales s
            JOIN customers c ON s.customer_id = c.id
            WHERE s.date BETWEEN ? AND ?
            GROUP BY c.id
            ORDER BY total_spent DESC
            LIMIT 10
        """, (start, end))
        data = cursor.fetchall()

        report_window = ctk.CTkToplevel(self.window)
        report_window.title("Top Customers")
        report_window.geometry("400x300")

        tree = ttk.Treeview(report_window, columns=("Customer", "Total Spent"), show="headings")
        tree.heading("Customer", text="Customer")
        tree.heading("Total Spent", text="Total Spent")
        tree.column("Customer", width=150)
        tree.column("Total Spent", width=150)
        for row in data:
            tree.insert("", "end", values=(row[0], f"${row[1]:.2f}"))
        tree.pack(fill="both", expand=True)

    # User Management Section
    def create_users(self):
        frame = self.content_frames['users']
        frame.configure(fg_color="#FFFFFF")

        form_frame = ctk.CTkFrame(frame, fg_color="transparent")
        form_frame.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(form_frame, text="Full Name:", font=("Arial", 14, "bold")).grid(row=0, column=0, padx=5, pady=5)
        self.new_full_name = ctk.CTkEntry(form_frame, width=200, height=40, font=("Arial", 14))
        self.new_full_name.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(form_frame, text="Email:", font=("Arial", 14, "bold")).grid(row=1, column=0, padx=5, pady=5)
        self.new_email = ctk.CTkEntry(form_frame, width=200, height=40, font=("Arial", 14))
        self.new_email.grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkLabel(form_frame, text="Username:", font=("Arial", 14, "bold")).grid(row=2, column=0, padx=5, pady=5)
        self.new_username = ctk.CTkEntry(form_frame, width=200, height=40, font=("Arial", 14))
        self.new_username.grid(row=2, column=1, padx=5, pady=5)

        ctk.CTkLabel(form_frame, text="Password:", font=("Arial", 14, "bold")).grid(row=3, column=0, padx=5, pady=5)
        self.new_password = ctk.CTkEntry(form_frame, show="*", width=200, height=40, font=("Arial", 14))
        self.new_password.grid(row=3, column=1, padx=5, pady=5)

        ctk.CTkLabel(form_frame, text="Role:", font=("Arial", 14, "bold")).grid(row=4, column=0, padx=5, pady=5)
        self.new_role = ctk.CTkComboBox(form_frame, values=["staff", "admin"], width=200, height=40, font=("Arial", 14))
        self.new_role.grid(row=4, column=1, padx=5, pady=5)

        ctk.CTkButton(form_frame, text="Add User", command=self.add_user, height=40, font=("Arial", 14)).grid(row=5, column=0, columnspan=2, pady=10)

        self.user_tree = ttk.Treeview(frame, columns=("ID", "Full Name", "Email", "Username", "Role"), show="headings")
        for col in self.user_tree["columns"]:
            self.user_tree.heading(col, text=col)
            self.user_tree.column(col, width=150)
        self.user_tree.pack(fill="both", expand=True, padx=20, pady=10)
        self.load_users()

    def add_user(self):
        full_name = self.new_full_name.get().strip()
        email = self.new_email.get().strip()
        username = self.new_username.get().strip()
        password = self.new_password.get()
        role = self.new_role.get()

        if not all([full_name, email, username, password, role]):
            messagebox.showerror("Error", "All fields are required")
            return

        if len(password) < 6:
            messagebox.showerror("Error", "Password must be at least 6 characters")
            return

        hashed = hashlib.sha256(password.encode()).hexdigest()
        try:
            cursor.execute("INSERT INTO users (full_name, email, username, password, role) VALUES (?, ?, ?, ?, ?)", (full_name, email, username, hashed, role))
            conn.commit()
            self.load_users()
            self.new_full_name.delete(0, "end")
            self.new_email.delete(0, "end")
            self.new_username.delete(0, "end")
            self.new_password.delete(0, "end")
            messagebox.showinfo("Success", "User added")
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Username already exists")

    def load_users(self):
        for item in self.user_tree.get_children():
            self.user_tree.delete(item)
        cursor.execute("SELECT id, full_name, email, username, role FROM users")
        for row in cursor.fetchall():
            self.user_tree.insert("", "end", values=row)

    # Settings Section
    def create_settings(self):
        frame = self.content_frames['settings']
        frame.configure(fg_color="#FFFFFF")

        form_frame = ctk.CTkFrame(frame, fg_color="transparent")
        form_frame.pack(pady=20, padx=20, fill="both", expand=True)

        settings_keys = [
            ('shop_name', 'Shop Name'),
            ('shop_phone', 'Shop Phone'),
            ('shop_email', 'Shop Email'),
            ('shop_location', 'Shop Location'),
            ('greeting_message', 'Greeting Message'),
            ('email_server', 'Email Server'),
            ('email_port', 'Email Port'),
            ('email_username', 'Email Username'),
            ('email_password', 'Email Password'),
            ('alert_email', 'Alert Email')
        ]

        self.settings_entries = {}
        for i, (key, label_text) in enumerate(settings_keys):
            ctk.CTkLabel(form_frame, text=label_text, font=("Arial", 14, "bold")).grid(row=i, column=0, padx=5, pady=5, sticky="e")
            entry = ctk.CTkEntry(form_frame, font=("Arial", 14), width=300, height=40)
            if key == 'email_password':
                entry.configure(show="*")
            entry.insert(0, self.get_setting(key, 'smtp.example.com' if key == 'email_server' else '587' if key == 'email_port' else ''))
            entry.grid(row=i, column=1, padx=5, pady=5)
            self.settings_entries[key] = entry

        row = len(settings_keys)
        ctk.CTkLabel(form_frame, text="Appearance Mode:", font=("Arial", 14, "bold")).grid(row=row, column=0, padx=5, pady=5, sticky="e")
        self.appearance_mode = ctk.CTkComboBox(form_frame, width=300, height=40, values=["System", "Light", "Dark"], font=("Arial", 14))
        self.appearance_mode.set(self.get_setting('appearance_mode', 'System'))
        self.appearance_mode.grid(row=row, column=1, padx=5, pady=5)

        row += 1
        ctk.CTkLabel(form_frame, text="Shop Logo:", font=("Arial", 14, "bold")).grid(row=row, column=0, padx=5, pady=5, sticky="e")
        self.shop_logo_label = ctk.CTkLabel(form_frame, text=self.get_setting('shop_logo', 'No logo'), font=("Arial", 14))
        self.shop_logo_label.grid(row=row, column=1, padx=5, pady=5)
        ctk.CTkButton(form_frame, text="Upload Logo", command=self.upload_shop_logo, height=40, font=("Arial", 14)).grid(row=row, column=2, padx=5, pady=5)

        row += 1
        ctk.CTkLabel(form_frame, text="Logo Horizontal Position:", font=("Arial", 14, "bold")).grid(row=row, column=0, padx=5, pady=5, sticky="e")
        self.logo_horizontal = ctk.CTkComboBox(form_frame, values=["Left", "Center", "Right"], width=100, height=40, font=("Arial", 14))
        self.logo_horizontal.set(self.get_setting('logo_horizontal', 'Left'))
        self.logo_horizontal.grid(row=row, column=1, padx=5, pady=5)

        row += 1
        ctk.CTkLabel(form_frame, text="Logo Vertical Position:", font=("Arial", 14, "bold")).grid(row=row, column=0, padx=5, pady=5, sticky="e")
        self.logo_vertical = ctk.CTkComboBox(form_frame, values=["Top", "Middle", "Bottom"], width=100, height=40, font=("Arial", 14))
        self.logo_vertical.set(self.get_setting('logo_vertical', 'Top'))
        self.logo_vertical.grid(row=row, column=1, padx=5, pady=5)

        row += 1
        ctk.CTkLabel(form_frame, text="Shop Info Alignment:", font=("Arial", 14, "bold")).grid(row=row, column=0, padx=5, pady=5, sticky="e")
        self.shop_info_alignment = ctk.CTkComboBox(form_frame, values=["Left", "Center", "Right"], width=100, height=40, font=("Arial", 14))
        self.shop_info_alignment.set(self.get_setting('shop_info_alignment', 'Center'))
        self.shop_info_alignment.grid(row=row, column=1, padx=5, pady=5)

        ctk.CTkButton(form_frame, text="Save Settings", command=self.save_settings, height=40, font=("Arial", 14)).grid(row=row+1, column=0, columnspan=2, pady=20)

    def upload_shop_logo(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png *.gif")])
        if file_path:
            try:
                img = Image.open(file_path)
                filename = os.path.basename(file_path)
                dest_path = os.path.join("images", filename)
                if not os.path.exists("images"):
                    os.makedirs("images")
                img.save(dest_path)
                self.set_setting('shop_logo', filename)
                self.shop_logo_label.configure(text=filename)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to upload logo: {e}")

    def save_settings(self):
        for key, entry in self.settings_entries.items():
            value = entry.get().strip()
            self.set_setting(key, value)
        appearance_mode = self.appearance_mode.get()
        self.set_setting('appearance_mode', appearance_mode)
        ctk.set_appearance_mode(appearance_mode)
        logo_horizontal = self.logo_horizontal.get()
        logo_vertical = self.logo_vertical.get()
        shop_info_alignment = self.shop_info_alignment.get()
        self.set_setting('logo_horizontal', logo_horizontal)
        self.set_setting('logo_vertical', logo_vertical)
        self.set_setting('shop_info_alignment', shop_info_alignment)
        messagebox.showinfo("Success", "Settings saved")

# Run Application
if __name__ == "__main__":
    import threading
    import uvicorn
    from socketio import ASGIApp

    app = ASGIApp(sio)

    def run_server():
        uvicorn.run(app, host="127.0.0.1", port=5000)

    threading.Thread(target=run_server, daemon=True).start()
    LoginWindow()