import customtkinter as ctk
from tkinter import ttk, messagebox, Menu
import sqlite3
import hashlib
import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from PIL import Image
from fpdf import FPDF

# Configuration
ctk.set_default_color_theme("blue")

# ----------------------------- Database Setup -----------------------------
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
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
    )''',
    '''CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        loyalty_points INTEGER DEFAULT 0 CHECK(loyalty_points >= 0)
    )''',
    '''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    )'''
]

for table in tables:
    cursor.execute(table)
conn.commit()

# ----------------------------- Login Window -----------------------------
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
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                           (username, hashed, 'admin'))
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
            MainApp(user[3], user[1])  # role and username
        else:
            messagebox.showerror("Error", "Invalid credentials")

# ----------------------------- Main Application -----------------------------
class MainApp:
    def __init__(self, role='staff', username=''):
        self.window = ctk.CTk()
        self.window.title("Shop Management System")
        self.window.geometry("1200x800")
        self.role = role
        self.username = username

        # Load appearance mode from settings
        appearance_mode = self.get_setting('appearance_mode', 'System')
        ctk.set_appearance_mode(appearance_mode)

        # Style treeviews
        style = ttk.Style()
        style.configure("Treeview", font=("Arial", 20), rowheight=25)
        style.configure("Treeview.Heading", font=("Arial", 20, "bold"))
        style.map("Treeview", background=[('selected', '#4682B4')])

        # Menubar
        menubar = Menu(self.window)
        self.window.config(menu=menubar)
        file_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Logout", font=("bold", 14), command=self.logout)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", font=("bold", 14), command=self.window.quit)

        # Sidebar with icons
        self.sidebar = ctk.CTkFrame(self.window, width=300, fg_color="#F0F0F0")
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
                                   fg_color="transparent", hover_color="#D3D3D3",
                                   text_color="#000000", command=command, font=("Arial", 20))
            button.pack(fill="x", padx=10, pady=5)
            self.nav_buttons[key] = button

        # Content frames
        self.content_frames = {}
        for section in [s[0] for s in sections]:
            self.content_frames[section] = ctk.CTkFrame(self.window)

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

        # Status bar
        status_bar = ctk.CTkFrame(self.window, height=30, fg_color="#E0E0E0")
        status_bar.pack(side="bottom", fill="x")
        ctk.CTkLabel(status_bar, text=f"Logged in as: {self.username}", font=("bold", 20)).pack(side="left", padx=10)
        ctk.CTkLabel(status_bar, text=datetime.date.today().strftime("%Y-%m-%d"), font=("bold", 25)).pack(side="right", padx=10)

        # Key bindings
        self.window.bind("<Control-1>", lambda event: self.show_dashboard())
        self.window.bind("<Control-2>", lambda event: self.show_products())
        self.window.bind("<Control-3>", lambda event: self.show_customers())
        self.window.bind("<Control-4>", lambda event: self.show_sales())
        self.window.bind("<Control-5>", lambda event: self.show_history())

        # Auto-refresh dashboard
        self.window.after(300000, self.refresh_dashboard)

        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.window.mainloop()

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

    def refresh_dashboard(self):
        self.update_dashboard()
        self.window.after(300000, self.refresh_dashboard)

    def get_setting(self, key, default=''):
        cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
        result = cursor.fetchone()
        return result[0] if result else default

    def set_setting(self, key, value):
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()

    # ### Dashboard Section
    def create_dashboard(self):
        frame = self.content_frames['dashboard']
        frame.configure(fg_color="#FFFFFF")

        stats_frame = ctk.CTkFrame(frame, fg_color="transparent")
        stats_frame.pack(pady=10, fill="x", padx=20)

        self.stats_labels = {
            'products': ctk.CTkLabel(stats_frame, text="Products: 0", font=("Arial", 20)),
            'customers': ctk.CTkLabel(stats_frame, text="Customers: 0", font=("Arial", 20)),
            'sales': ctk.CTkLabel(stats_frame, text="Sales: 0", font=("Arial", 20)),
            'revenue': ctk.CTkLabel(stats_frame, text="Revenue: $0.00", font=("Arial", 20)),
            'expenses': ctk.CTkLabel(stats_frame, text="Expenses: $0.00", font=("Arial", 20))
        }

        for i, label in enumerate(self.stats_labels.values()):
            label.grid(row=0, column=i, padx=20, pady=5)

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

        for item in self.alert_tree.get_children():
            self.alert_tree.delete(item)
        cursor.execute("SELECT name, quantity FROM products WHERE quantity < min_stock")
        low_stock = cursor.fetchall()
        if low_stock:
            for name, qty in low_stock:
                self.alert_tree.insert("", "end", values=(name, qty))
            self.alert_frame.pack(pady=10, padx=20, fill="x")
        else:
            self.alert_frame.pack_forget()

    # ### Products Section
    def create_products(self):
        frame = self.content_frames['products']
        frame.configure(fg_color="#FFFFFF")

        search_frame = ctk.CTkFrame(frame, fg_color="transparent")
        search_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(search_frame, text="Search:", font=("Arial", 25)).pack(side="left", padx=5)
        self.product_search = ctk.CTkEntry(search_frame, height=50, font=("Arial", 20))
        self.product_search.pack(side="left", fill="x", expand=True, padx=5)
        self.product_search.bind("<KeyRelease>", self.filter_products)

        form_frame = ctk.CTkFrame(frame, fg_color="transparent")
        form_frame.pack(pady=10, padx=20, fill="x")

        entries = [
            ("Name", "name", lambda m: ctk.CTkEntry(m,height=50, width=200, font=("Arial", 20))),
            ("Category", "category", lambda m: ctk.CTkComboBox(m, values=[
                "Laptop", "Monitor", "CPU", "GPU", "RAM", "Storage", "Motherboard",
                "Power Supply", "Case", "Keyboard", "Mouse", "Printer", "Accessories"
            ],height=50, width=200, font=("Arial", 20))),
            ("Quantity", "quantity", lambda m: ctk.CTkEntry(m,height=50, width=200, font=("Arial", 20))),
            ("Price", "price", lambda m: ctk.CTkEntry(m,height=50, width=200, font=("Arial", 20))),
            ("Min Stock", "min_stock", lambda m: ctk.CTkEntry(m, height=50, width=200,font=("Arial", 20))),
            ("Supplier", "supplier", lambda m: ctk.CTkComboBox(m,height=50, width=200, font=("Arial", 20)))
        ]

        self.product_entries = {}
        for i, (label_text, key, widget_type) in enumerate(entries):
            ctk.CTkLabel(form_frame, text=label_text, font=("Arial", 20)).grid(row=0, column=i, padx=5, pady=5)
            entry = widget_type(form_frame)
            if key == 'supplier':
                self.load_suppliers_combobox(entry)
            entry.grid(row=1, column=i, padx=5, pady=5)
            self.product_entries[key] = entry

        button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        button_frame.pack(pady=5)
        self.add_update_product_button = ctk.CTkButton(button_frame, text="Add Product", command=self.add_or_update_product, height=50, font=("Arial", 18))
        self.add_update_product_button.pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Delete Product", command=self.delete_product, fg_color="#d9534f", hover_color="#c9302c",height=50, font=("Arial", 18)).pack(side="left", padx=5)

        self.product_tree = ttk.Treeview(frame, columns=("ID", "Name", "Category", "Qty", "Price", "Min Stock", "Supplier"), show="headings")
        for col in self.product_tree["columns"]:
            self.product_tree.heading(col, text=col)
            self.product_tree.column(col, width=100)
        self.product_tree.pack(fill="both", expand=True, padx=20, pady=10)
        self.product_tree.bind("<Double-1>", self.select_product)
        self.load_products()

        self.selected_product_id = None

    def load_suppliers_combobox(self, combobox):
        cursor.execute("SELECT name FROM suppliers")
        suppliers = ["None"] + [row[0] for row in cursor.fetchall()]
        combobox.configure(values=suppliers)
        combobox.set("None")

    def load_products(self):
        for item in self.product_tree.get_children():
            self.product_tree.delete(item)
        cursor.execute("SELECT p.id, p.name, p.category, p.quantity, p.price, p.min_stock, s.name FROM products p LEFT JOIN suppliers s ON p.supplier_id = s.id")
        for row in cursor.fetchall():
            self.product_tree.insert("", "end", values=row)

    def filter_products(self, event):
        search_term = self.product_search.get().lower()
        for item in self.product_tree.get_children():
            self.product_tree.delete(item)
        cursor.execute("SELECT p.id, p.name, p.category, p.quantity, p.price, p.min_stock, s.name FROM products p LEFT JOIN suppliers s ON p.supplier_id = s.id WHERE LOWER(p.name) LIKE ?", (f"%{search_term}%",))
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
            self.add_update_product_button.configure(text="Update Product")

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

        if not all([name, category, quantity, price, min_stock]):
            messagebox.showerror("Error", "All fields are required")
            return

        try:
            quantity = int(quantity)
            price = float(price)
            min_stock = int(min_stock)
            if quantity < 0 or price < 0 or min_stock < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Quantity, price, and min stock must be positive numbers")
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
            cursor.execute("UPDATE products SET name=?, category=?, quantity=?, price=?, min_stock=?, supplier_id=? WHERE id=?",
                           (name, category, quantity, price, min_stock, supplier_id, self.selected_product_id))
            conn.commit()
            self.load_products()
            self.update_dashboard()
            messagebox.showinfo("Success", "Product updated")
            self.clear_product_form()
        else:
            cursor.execute("INSERT INTO products (name, category, quantity, price, min_stock, supplier_id) VALUES (?, ?, ?, ?, ?, ?)",
                           (name, category, quantity, price, min_stock, supplier_id))
            conn.commit()
            self.load_products()
            self.update_dashboard()
            messagebox.showinfo("Success", "Product added")
            self.clear_product_form()

    def clear_product_form(self):
        self.product_entries['name'].delete(0, "end")
        self.product_entries['category'].set("Laptop")
        self.product_entries['quantity'].delete(0, "end")
        self.product_entries['price'].delete(0, "end")
        self.product_entries['min_stock'].delete(0, "end")
        self.product_entries['supplier'].set("None")
        self.selected_product_id = None
        self.add_update_product_button.configure(text="Add Product")

    # ### Customers Section
    def create_customers(self):
        frame = self.content_frames['customers']
        frame.configure(fg_color="#FFFFFF")

        search_frame = ctk.CTkFrame(frame, fg_color="transparent")
        search_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(search_frame, text="Search:", font=("Arial", 30)).pack(side="left", padx=5)
        self.customer_search = ctk.CTkEntry(search_frame, height=50, font=("Arial", 30))
        self.customer_search.pack(side="left", fill="x", expand=True, padx=5)
        self.customer_search.bind("<KeyRelease>", self.filter_customers)

        form_frame = ctk.CTkFrame(frame, fg_color="transparent")
        form_frame.pack(pady=10, padx=20, fill="x")

        entries = [("Name", "name"), ("Phone", "phone"), ("Email", "email"), ("Points", "points")]
        self.customer_entries = {}
        for i, (label_text, key) in enumerate(entries):
            ctk.CTkLabel(form_frame, text=label_text, font=("Arial", 20)).grid(row=0, column=i, padx=5, pady=5)
            entry = ctk.CTkEntry(form_frame,height=50, width=300, font=("Arial", 20))

            entry.grid(row=3, column=i, padx=5, pady=5)
            self.customer_entries[key] = entry

        button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        button_frame.pack(pady=5)
        self.add_update_customer_button = ctk.CTkButton(button_frame, text="Add Customer", command=self.add_or_update_customer, height=50,width=100, font=("Arial", 20))
        self.add_update_customer_button.pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Delete Customer", command=self.delete_customer,fg_color="#d9534f", hover_color="#c9302c",height=50, width=100, font=("Arial", 20)).pack(side="left", padx=5)

        self.customer_tree = ttk.Treeview(frame, columns=("ID", "Name", "Phone", "Email", "Points"), show="headings")
        for col in self.customer_tree["columns"]:
            self.customer_tree.heading(col, text=col)
            self.customer_tree.column(col, width=120)
        self.customer_tree.pack(fill="both", expand=True, padx=20, pady=10)
        self.customer_tree.bind("<Double-1>", self.select_customer)
        self.load_customers()

        ctk.CTkButton(frame, text="Generate Customer Report", command=self.generate_customer_report, height=50, width=130, font=("Arial", 20)).pack(pady=10)

        self.selected_customer_id = None

    def load_customers(self):
        for item in self.customer_tree.get_children():
            self.customer_tree.delete(item)
        cursor.execute("SELECT id, name, phone, email, loyalty_points FROM customers")
        for row in cursor.fetchall():
            self.customer_tree.insert("", "end", values=row)

    def filter_customers(self, event):
        search_term = self.customer_search.get().lower()
        for item in self.customer_tree.get_children():
            self.customer_tree.delete(item)
        cursor.execute("SELECT id, name, phone, email, loyalty_points FROM customers WHERE LOWER(name) LIKE ?", (f"%{search_term}%",))
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
                messagebox.showinfo("Success", "Customer deleted")
        else:
            messagebox.showwarning("Warning", "Please select a customer")

    def add_or_update_customer(self):
        name = self.customer_entries['name'].get().strip()
        phone = self.customer_entries['phone'].get().strip()
        email = self.customer_entries['email'].get().strip()
        points = self.customer_entries['points'].get().strip() or "0"

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
            cursor.execute("UPDATE customers SET name=?, phone=?, email=?, loyalty_points=? WHERE id=?",
                           (name, phone, email, points, self.selected_customer_id))
            conn.commit()
            self.load_customers()
            self.update_dashboard()
            messagebox.showinfo("Success", "Customer updated")
            self.clear_customer_form()
        else:
            cursor.execute("INSERT INTO customers (name, phone, email, loyalty_points) VALUES (?, ?, ?, ?)",
                           (name, phone, email, points))
            conn.commit()
            self.load_customers()
            self.update_dashboard()
            messagebox.showinfo("Success", "Customer added")
            self.clear_customer_form()

    def clear_customer_form(self):
        for entry in self.customer_entries.values():
            entry.delete(0, "end")
        self.selected_customer_id = None
        self.add_update_customer_button.configure(text="Add Customer")

    def generate_customer_report(self):
        selected = self.customer_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a customer")
            return
        item = self.customer_tree.item(selected[0])
        customer_id = item['values'][0]
        cursor.execute("SELECT name, phone, email, loyalty_points FROM customers WHERE id=?", (customer_id,))
        customer = cursor.fetchone()
        if not customer:
            messagebox.showerror("Error", "Customer not found")
            return
        name, phone, email, points = customer

        cursor.execute("SELECT s.id, s.date, s.total, s.discount FROM sales s WHERE s.customer_id=?", (customer_id,))
        sales = cursor.fetchall()

        shop_name = self.get_setting('shop_name', 'My Shop')
        shop_phone = self.get_setting('shop_phone', '')
        shop_email = self.get_setting('shop_email', '')
        greeting_message = self.get_setting('greeting_message', 'Thank you for your purchase!')

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        pdf.cell(200, 10, txt=shop_name, ln=True, align='C')
        if shop_phone:
            pdf.cell(200, 10, txt=f"Phone: {shop_phone}", ln=True, align='C')
        if shop_email:
            pdf.cell(200, 10, txt=f"Email: {shop_email}", ln=True, align='C')
        pdf.ln(10)

        pdf.cell(200, 10, txt="Customer Report", ln=True, align='C')
        pdf.ln(10)

        pdf.cell(200, 10, txt=f"Customer: {name}", ln=True)
        pdf.cell(200, 10, txt=f"Phone: {phone}", ln=True)
        pdf.cell(200, 10, txt=f"Email: {email}", ln=True)
        pdf.cell(200, 10, txt=f"Loyalty Points: {points}", ln=True)
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
        messagebox.showinfo("Success", f"Customer report generated: {pdf_file}")

    # ### Sales Section
    def create_sales(self):
        frame = self.content_frames['sales']
        frame.configure(fg_color="#FFFFFF")

        customer_frame = ctk.CTkFrame(frame, fg_color="transparent")
        customer_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(customer_frame, text="Customer:", font=("bold", 20)).pack(side="left", padx=5)
        self.customer_combobox = ctk.CTkComboBox(customer_frame, width= 300, height=50, font=("bold", 20))
        self.load_customers_combobox()
        self.customer_combobox.pack(side="left", padx=5)

        add_frame = ctk.CTkFrame(frame, fg_color="transparent")
        add_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(add_frame, text="Product:", font=("bold", 20)).pack(side="left", padx=5)
        self.product_combobox = ctk.CTkComboBox(add_frame,width= 300, height=50, font=("bold", 20))
        self.load_products_combobox()
        self.product_combobox.pack(side="left", padx=5)
        ctk.CTkLabel(add_frame, text="Quantity:", font=("bold", 20)).pack(side="left", padx=5)
        self.quantity_entry = ctk.CTkEntry(add_frame, width=300, height=50, font=("bold", 20))
        self.quantity_entry.pack(side="left", padx=5)
        ctk.CTkButton(add_frame, text="Add to Sale", command=self.add_to_sale, width=130 , height=50, font=("Arial", 20)).pack(side="left", padx=10)

        self.sale_tree = ttk.Treeview(frame, columns=("Product", "Quantity", "Price", "Subtotal"), show="headings")
        for col in self.sale_tree["columns"]:
            self.sale_tree.heading(col, text=col)
            self.sale_tree.column(col, width=150)
        self.sale_tree.pack(fill="both", expand=True, padx=20, pady=10)

        total_frame = ctk.CTkFrame(frame, fg_color="transparent")
        total_frame.pack(pady=10, padx=20, fill="x")
        self.subtotal_label = ctk.CTkLabel(total_frame, text="Subtotal: $0.00", font=("bold", 29))
        self.subtotal_label.pack(side="left", padx=10)
        ctk.CTkLabel(total_frame, text="Discount (%):", font=("bold", 29)).pack(side="left", padx=5)
        self.discount_entry = ctk.CTkEntry(total_frame, width=120, height=50, font=("Arial", 20))
        self.discount_entry.pack(side="left", padx=5)
        ctk.CTkButton(total_frame, text="Apply", command=self.apply_discount, width=120,height=50, font=("Arial", 20)).pack(side="left", padx=5)
        self.total_label = ctk.CTkLabel(total_frame, text="Total: $0.00", font=("Arial", 29))
        self.total_label.pack(side="left", padx=10)

        ctk.CTkButton(frame, text="Finalize Sale", command=self.finalize_sale, height=50, width=130,font=("Arial", 20)).pack(pady=10)

        self.current_sale_items = []
        self.current_discount = 0.0

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

        cursor.execute("SELECT id, name, quantity, price FROM products WHERE name=?", (product_name,))
        product = cursor.fetchone()
        if not product:
            messagebox.showerror("Error", "Product not found")
            return

        product_id, name, available_qty, price = product
        if quantity > available_qty:
            messagebox.showerror("Error", f"Insufficient stock. Available: {available_qty}")
            return

        subtotal_item = quantity * price
        self.sale_tree.insert("", "end", values=(name, quantity, f"${price:.2f}", f"${subtotal_item:.2f}"))

        self.current_sale_items.append({'id': product_id, 'name': name, 'quantity': quantity, 'price': price})
        self.quantity_entry.delete(0, "end")

        subtotal = sum(item['quantity'] * item['price'] for item in self.current_sale_items)
        self.subtotal_label.configure(text=f"Subtotal: ${subtotal:.2f}")
        total = subtotal * (1 - self.current_discount / 100)
        self.total_label.configure(text=f"Total: ${total:.2f}")

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
        subtotal = sum(item['quantity'] * item['price'] for item in self.current_sale_items)
        total = subtotal * (1 - self.current_discount / 100)
        self.total_label.configure(text=f"Total: ${total:.2f}")

    def finalize_sale(self):
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
        cursor.execute("INSERT INTO sales (customer_id, date, total, discount) VALUES (?, ?, ?, ?)",
                       (customer_id, date, total, self.current_discount))
        sale_id = cursor.lastrowid

        for item in self.current_sale_items:
            cursor.execute("INSERT INTO sale_items (sale_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                           (sale_id, item['id'], item['quantity'], item['price']))
            cursor.execute("UPDATE products SET quantity = quantity - ? WHERE id = ?",
                           (item['quantity'], item['id']))

        points_earned = int(total // 10)
        cursor.execute("UPDATE customers SET loyalty_points = loyalty_points + ? WHERE id = ?",
                       (points_earned, customer_id))

        conn.commit()
        self.sale_tree.delete(*self.sale_tree.get_children())
        self.subtotal_label.configure(text="Subtotal: $0.00")
        self.total_label.configure(text="Total: $0.00")
        self.discount_entry.delete(0, "end")
        self.current_sale_items = []
        self.current_discount = 0.0
        self.update_dashboard()
        self.load_sales_history()
        messagebox.showinfo("Success", "Sale completed successfully")

    # ### Sales History Section
    def create_history(self):
        frame = self.content_frames['history']
        frame.configure(fg_color="#FFFFFF")

        self.history_tree = ttk.Treeview(frame, columns=("ID", "Date", "Customer", "Total"), show="headings")
        for col in self.history_tree["columns"]:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=150)
        self.history_tree.pack(fill="both", expand=True, padx=20, pady=20)
        self.load_sales_history()

        ctk.CTkButton(frame, text="Generate Receipt", command=self.generate_receipt, width=120, height=50,font=("Arial", 20)).pack(pady=10)

    def load_sales_history(self):
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        cursor.execute("SELECT s.id, s.date, c.name, s.total FROM sales s JOIN customers c ON s.customer_id = c.id")
        for row in cursor.fetchall():
            self.history_tree.insert("", "end", values=(row[0], row[1], row[2], f"${row[3]:.2f}"))

    def generate_receipt(self):
        selected = self.history_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a sale")
            return

        item = self.history_tree.item(selected[0])
        sale_id = item['values'][0]

        cursor.execute("SELECT s.date, c.name, s.total, s.discount FROM sales s JOIN customers c ON s.customer_id = c.id WHERE s.id=?", (sale_id,))
        sale = cursor.fetchone()
        date, customer_name, total, discount = sale

        cursor.execute("SELECT p.name, si.quantity, si.price FROM sale_items si JOIN products p ON si.product_id = p.id WHERE si.sale_id=?", (sale_id,))
        items = cursor.fetchall()

        shop_name = self.get_setting('shop_name', 'My Shop')
        shop_phone = self.get_setting('shop_phone', '')
        shop_email = self.get_setting('shop_email', '')
        greeting_message = self.get_setting('greeting_message', 'Thank you for your purchase!')

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        pdf.cell(200, 10, txt=shop_name, ln=True, align='C')
        if shop_phone:
            pdf.cell(200, 10, txt=f"Phone: {shop_phone}", ln=True, align='C')
        if shop_email:
            pdf.cell(200, 10, txt=f"Email: {shop_email}", ln=True, align='C')
        pdf.ln(10)

        pdf.cell(200, 10, txt=f"Sale ID: {sale_id}", ln=True)
        pdf.cell(200, 10, txt=f"Date: {date}", ln=True)
        pdf.cell(200, 10, txt=f"Customer: {customer_name}", ln=True)
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
        messagebox.showinfo("Success", f"Receipt generated: {pdf_file}")

    # ### Suppliers Section
    def create_suppliers(self):
        frame = self.content_frames['suppliers']
        frame.configure(fg_color="#FFFFFF")

        form_frame = ctk.CTkFrame(frame, fg_color="transparent")
        form_frame.pack(pady=10, padx=20, fill="x")

        entries = [("Name", "name"), ("Contact", "contact"), ("Email", "email"), ("Products", "products")]
        self.supplier_entries = {}
        for i, (label_text, key) in enumerate(entries):
            ctk.CTkLabel(form_frame, text=label_text, font=("Arial", 24)).grid(row=0, column=i, padx=5, pady=5)
            entry = ctk.CTkEntry(form_frame, height=50,width=300,font=("Arial", 20))
            entry.grid(row=1, column=i, padx=5, pady=5)
            self.supplier_entries[key] = entry

        button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        button_frame.pack(pady=5)
        self.add_update_supplier_button = ctk.CTkButton(button_frame, text="Add Supplier", command=self.add_or_update_supplier, width=130, height=50,font=("Arial", 24))
        self.add_update_supplier_button.pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Delete Supplier", command=self.delete_supplier,fg_color="#d9534f",hover_color="#c9302c",width=130,height=50,font=("Arial", 24)).pack(side="left", padx=5)

        self.supplier_tree = ttk.Treeview(frame, columns=("ID", "Name", "Contact", "Email", "Products"), show="headings")
        for col in self.supplier_tree["columns"]:
            self.supplier_tree.heading(col, text=col)
            self.supplier_tree.column(col, width=120)
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

    # ### Expenses Section
    def create_expenses(self):
        frame = self.content_frames['expenses']
        frame.configure(fg_color="#FFFFFF")

        form_frame = ctk.CTkFrame(frame, fg_color="transparent")
        form_frame.pack(pady=10, padx=20, fill="x")

        entries = [("Date", "date"), ("Category", "category"), ("Amount", "amount"), ("Description", "description")]
        self.expense_entries = {}
        for i, (label_text, key) in enumerate(entries):
            ctk.CTkLabel(form_frame, text=label_text, font=("Arial", 20)).grid(row=0, column=i, padx=5, pady=5)
            entry = ctk.CTkEntry(form_frame, width=200, height=50, placeholder_text="YYYY-MM-DD" if key == 'date' else "", font=("Arial", 24))
            entry.grid(row=1, column=i, padx=5, pady=5)
            self.expense_entries[key] = entry

        ctk.CTkButton(form_frame, text="Add Expense",width=120, height=50 ,command=self.add_expense, font=("Arial", 20)).grid(row=1, column=len(entries), padx=10, pady=5)

        self.expense_tree = ttk.Treeview(frame, columns=("ID", "Date", "Category", "Amount", "Description"), show="headings")
        for col in self.expense_tree["columns"]:
            self.expense_tree.heading(col, text=col)
            self.expense_tree.column(col, width=120)
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

        cursor.execute("INSERT INTO expenses (date, category, amount, description) VALUES (?, ?, ?, ?)",
                       (date, category, amount, description))
        conn.commit()
        self.load_expenses()
        self.update_dashboard()
        messagebox.showinfo("Success", "Expense added")

    # ### Purchase Orders Section
    def create_purchase_orders(self):
        frame = self.content_frames['purchase_orders']
        frame.configure(fg_color="#FFFFFF")

        form_frame = ctk.CTkFrame(frame, fg_color="transparent")
        form_frame.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(form_frame, text="Supplier:", font=("Arial", 24)).grid(row=0, column=0, padx=5, pady=5)
        self.po_supplier = ctk.CTkComboBox(form_frame, width=200, height=50, font=("Arial", 20))
        self.load_suppliers_combobox(self.po_supplier)
        self.po_supplier.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(form_frame, text="Product:", font=("Arial", 24)).grid(row=1, column=0, padx=5, pady=5)
        self.po_product = ctk.CTkComboBox(form_frame, width=200, height=50, font=("Arial", 20))
        self.load_products_combobox_po()
        self.po_product.grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkLabel(form_frame, text="Quantity:", font=("Arial", 24)).grid(row=2, column=0, padx=5, pady=5)
        self.po_quantity = ctk.CTkEntry(form_frame,width=200, height=50, font=("Arial", 20))
        self.po_quantity.grid(row=2, column=1, padx=5, pady=5)

        ctk.CTkButton(form_frame, text="Add to Order", command=self.add_to_po, width=130, height=50, font=("Arial", 20)).grid(row=3, column=0, columnspan=2, pady=5)

        self.po_items_tree = ttk.Treeview(frame, columns=("Product", "Quantity"), show="headings")
        self.po_items_tree.heading("Product", text="Product")
        self.po_items_tree.heading("Quantity", text="Quantity")
        self.po_items_tree.column("Product", width=200)
        self.po_items_tree.column("Quantity", width=100)
        self.po_items_tree.pack(fill="x", padx=20, pady=10)

        ctk.CTkButton(frame, text="Create Purchase Order", command=self.create_po, font=("Arial", 12)).pack(pady=5)

        self.po_tree = ttk.Treeview(frame, columns=("ID", "Supplier", "Date", "Status"), show="headings")
        for col in self.po_tree["columns"]:
            self.po_tree.heading(col, text=col)
            self.po_tree.column(col, width=150)
        self.po_tree.pack(fill="both", expand=True, padx=20, pady=10)
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
        cursor.execute("INSERT INTO purchase_orders (supplier_id, date, status) VALUES (?, ?, ?)",
                       (supplier_id, date, "Pending"))
        po_id = cursor.lastrowid

        for item in self.current_po_items:
            cursor.execute("INSERT INTO purchase_order_items (po_id, product_id, quantity) VALUES (?, ?, ?)",
                           (po_id, item['id'], item['quantity']))

        conn.commit()
        self.po_items_tree.delete(*self.po_items_tree.get_children())
        self.current_po_items = []
        self.load_purchase_orders()
        messagebox.showinfo("Success", "Purchase order created")

    def load_purchase_orders(self):
        for item in self.po_tree.get_children():
            self.po_tree.delete(item)
        cursor.execute("SELECT po.id, s.name, po.date, po.status FROM purchase_orders po JOIN suppliers s ON po.supplier_id = s.id")
        for row in cursor.fetchall():
            self.po_tree.insert("", "end", values=row)

    # ### Reports Section
    def create_reports(self):
        frame = self.content_frames['reports']
        frame.configure(fg_color="#FFFFFF")

        date_frame = ctk.CTkFrame(frame, fg_color="transparent")
        date_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(date_frame, text="From:", font=("Arial", 24)).pack(side="left", padx=5)
        self.start_date = ctk.CTkEntry(date_frame, placeholder_text="YYYY-MM-DD", width=200, height=50,font=("Arial", 20))
        self.start_date.pack(side="left", padx=5)
        ctk.CTkLabel(date_frame, text="To:", font=("Arial", 24)).pack(side="left", padx=5)
        self.end_date = ctk.CTkEntry(date_frame, placeholder_text="YYYY-MM-DD", width=200, height=50, font=("Arial", 20))
        self.end_date.pack(side="left", padx=5)
        ctk.CTkButton(date_frame, text="Generate", command=self.generate_report,width=120, height=50, font=("Arial", 20)).pack(side="left", padx=10)

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

    # ### User Management Section
    def create_users(self):
        frame = self.content_frames['users']
        frame.configure(fg_color="#FFFFFF")

        form_frame = ctk.CTkFrame(frame, fg_color="transparent")
        form_frame.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(form_frame, text="Username:", font=("Arial", 24)).grid(row=0, column=0, padx=5, pady=5)
        self.new_username = ctk.CTkEntry(form_frame,width=200, height=50, font=("Arial", 24))
        self.new_username.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(form_frame, text="Password:", font=("Arial", 24)).grid(row=1, column=0, padx=5, pady=5)
        self.new_password = ctk.CTkEntry(form_frame, show="*", width=200, height=50,font=("Arial", 24))
        self.new_password.grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkLabel(form_frame, text="Role:", font=("Arial", 24)).grid(row=2, column=0, padx=5, pady=5)
        self.new_role = ctk.CTkComboBox(form_frame, values=["staff", "admin"],width=200, height=50, font=("Arial", 24))
        self.new_role.grid(row=2, column=1, padx=5, pady=5)

        ctk.CTkButton(form_frame, text="Add User", command=self.add_user, width=130, height=50, font=("Arial", 24)).grid(row=3, column=0, columnspan=2, pady=10)

        self.user_tree = ttk.Treeview(frame, columns=("ID", "Username", "Role"), show="headings")
        for col in self.user_tree["columns"]:
            self.user_tree.heading(col, text=col)
            self.user_tree.column(col, width=150)
        self.user_tree.pack(fill="both", expand=True, padx=20, pady=10)
        self.load_users()

    def add_user(self):
        username = self.new_username.get().strip()
        password = self.new_password.get()
        role = self.new_role.get()

        if not all([username, password, role]):
            messagebox.showerror("Error", "All fields are required")
            return

        if len(password) < 6:
            messagebox.showerror("Error", "Password must be at least 6 characters")
            return

        hashed = hashlib.sha256(password.encode()).hexdigest()
        try:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, hashed, role))
            conn.commit()
            self.load_users()
            self.new_username.delete(0, "end")
            self.new_password.delete(0, "end")
            messagebox.showinfo("Success", "User added")
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Username already exists")

    def load_users(self):
        for item in self.user_tree.get_children():
            self.user_tree.delete(item)
        cursor.execute("SELECT id, username, role FROM users")
        for row in cursor.fetchall():
            self.user_tree.insert("", "end", values=row)

    # ### Settings Section
    def create_settings(self):
        frame = self.content_frames['settings']
        frame.configure(fg_color="#FFFFFF")

        form_frame = ctk.CTkFrame(frame, fg_color="transparent")
        form_frame.pack(pady=20, padx=20, fill="both", expand=True)

        settings_keys = [
            ('shop_name', 'Shop Name'),
            ('shop_phone', 'Shop Phone'),
            ('shop_email', 'Shop Email'),
            ('greeting_message', 'Greeting Message')
        ]

        self.settings_entries = {}
        for i, (key, label_text) in enumerate(settings_keys):
            ctk.CTkLabel(form_frame, text=label_text, font=("Arial", 24)).grid(row=i, column=0, padx=5, pady=5, sticky="e")
            entry = ctk.CTkEntry(form_frame, font=("Arial", 24), width=300, height=50)
            entry.insert(0, self.get_setting(key))
            entry.grid(row=i, column=1, padx=5, pady=5)
            self.settings_entries[key] = entry

        row = len(settings_keys)
        ctk.CTkLabel(form_frame, text="Appearance Mode:", font=("Arial", 24)).grid(row=row, column=0, padx=5, pady=5, sticky="e")
        self.appearance_mode = ctk.CTkComboBox(form_frame, width=300, height=50, values=["System", "Light", "Dark"], font=("Arial", 24))
        self.appearance_mode.set(self.get_setting('appearance_mode', 'System'))
        self.appearance_mode.grid(row=row, column=1, padx=5, pady=5)

        ctk.CTkButton(form_frame, text="Save Settings", command=self.save_settings,width=130, height=50, font=("Arial", 24)).grid(row=row+1, column=0, columnspan=2, pady=20)

    def save_settings(self):
        for key, entry in self.settings_entries.items():
            value = entry.get().strip()
            self.set_setting(key, value)
        appearance_mode = self.appearance_mode.get()
        self.set_setting('appearance_mode', appearance_mode)
        ctk.set_appearance_mode(appearance_mode)
        messagebox.showinfo("Success", "Settings saved")

# ----------------------------- Run Application -----------------------------
if __name__ == "__main__":
    LoginWindow()