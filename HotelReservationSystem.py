import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import sqlite3  
from datetime import datetime, timedelta
import decimal
import sys
import csv
import os

DB_FILE = 'hotel_db.sqlite'

RESERVE_PERCENT = decimal.Decimal('0.20')

# -------------------- Database Utilities --------------------
def get_connection():
    """Connects to the local SQLite file."""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    except sqlite3.Error as e:
        messagebox.showerror('DB Error', f'Error connecting to SQLite: {e}')
        raise

def init_db_and_seed():
    """Creates tables if they don't exist and seeds initial data."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS staff_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT,
        username TEXT UNIQUE,
        password TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_number TEXT UNIQUE,
        room_type TEXT,
        prefix TEXT,
        base_price REAL,
        status TEXT DEFAULT 'VACANT',
        payment_status TEXT DEFAULT 'UNPAID'
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_number TEXT,
        action TEXT,
        staff TEXT,
        customer_name TEXT,
        amount REAL DEFAULT 0,
        notes TEXT,
        created_at TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS damages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_number TEXT,
        item_name TEXT,
        cost REAL,
        reported_by TEXT,
        report_time TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_number TEXT,
        customer_name TEXT,
        checkin_date TEXT,
        checkout_date TEXT,
        prepaid REAL DEFAULT 0,
        status TEXT DEFAULT 'ACTIVE'
    );
    """)

    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM rooms")
    count = cursor.fetchone()[0]
    if count == 0:
        seed_rooms(cursor)
        conn.commit()

    cursor.execute("SELECT COUNT(*) FROM staff_users")
    scount = cursor.fetchone()[0]
    if scount == 0:
        try:
            cursor.execute("INSERT INTO staff_users (full_name, username, password) VALUES (?,?,?)", ("Administrator","admin","admin"))
            conn.commit()
        except Exception:
            pass

    cursor.close()
    conn.close()

def seed_rooms(cursor):
    room_definitions = [
        ('Standard', 'STDROOM', 101, 120, 1500.00),
        ('Deluxe', 'DLXROOM', 121, 130, 2500.00),
        ('Suite', 'SUITEROOM', 201, 205, 4000.00),
        ('Connecting', 'CONN', 301, 310, 3000.00),
        ('Family', 'FAM', 401, 410, 3500.00),
        ('Single', 'SGL', 501, 510, 1000.00),
        ('Double', 'DBL', 511, 520, 1800.00),
        ('Twin', 'TWN', 521, 530, 2000.00),
    ]
    for rtype, prefix, start, end, price in room_definitions:
        for num in range(start, end + 1):
            room_number = f"{num}"
            cursor.execute(
                "INSERT INTO rooms (room_number, room_type, prefix, base_price, status, payment_status) VALUES (?,?,?,?,?,?)",
                (room_number, rtype, prefix, float(price), 'VACANT', 'UNPAID')
            )

# -------------------- GUI / App --------------------
class HotelApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Automated Hotel Room Booking and Reservation System')
        self.geometry('1160x700')
        self.minsize(980, 600)
        self.configure(bg='#eef5fb')

        self.style = ttk.Style(self)
        try:
            self.style.theme_use('clam')
        except Exception:
            pass

        base_font = ('Segoe UI', 10)
        header_font = ('Segoe UI', 15, 'bold')
        card_bg = '#f7fbff'   
        accent = '#2b6ea3'    
        muted = '#6b7c8a'     

        self.style.configure('.', font=base_font)
        self.style.configure('Header.TLabel', font=header_font, foreground=accent, background='#eaf4ff')
        self.style.configure('SubHeader.TLabel', font=('Segoe UI', 11, 'bold'), foreground=muted, background=card_bg)
        self.style.configure('Card.TFrame', background=card_bg, relief='flat')
        self.style.configure('CardAlt.TFrame', background='#ffffff', relief='flat')
        self.style.configure('Primary.TButton', background=accent, foreground='white', padding=8)
        self.style.map('Primary.TButton',
                       background=[('active', '#215c86'), ('!disabled', accent)])
        self.style.configure('Secondary.TButton', background='#dfeefb', foreground=accent, padding=6)
        self.style.configure('Treeview', rowheight=28, fieldbackground='#ffffff')
        self.style.configure('TEntry', padding=4)

        self.style.configure('TNotebook', background=self['bg'])
        self.style.configure('TNotebook.Tab', padding=[10,6], font=('Segoe UI', 10))

        init_db_and_seed()

        self.current_staff = None
        self.create_widgets()

    def create_widgets(self):
        header = ttk.Frame(self, padding=(12,10,12,10), style='CardAlt.TFrame')
        header.pack(fill='x', padx=12, pady=(12,6))
        header.configure(height=60)
        left_h = ttk.Frame(header, style='CardAlt.TFrame')
        left_h.pack(side='left', anchor='w')
        ttk.Label(left_h, text='Hotel Booking & Reservation System', style='Header.TLabel').pack(anchor='w')

        self.status_var = tk.StringVar(value='Not logged in')
        right_h = ttk.Frame(header, style='CardAlt.TFrame')
        right_h.pack(side='right', anchor='e')
        ttk.Label(right_h, textvariable=self.status_var).pack(anchor='e')

        content = ttk.Frame(self, padding=12, style='Card.TFrame')
        content.pack(fill='both', expand=True, padx=12, pady=(0,12))

        self.nb = ttk.Notebook(content)
        self.nb.pack(fill='both', expand=True, pady=6)

        self.page_customer = ttk.Frame(self.nb, padding=12)
        self.page_staff = ttk.Frame(self.nb, padding=12)
        self.nb.add(self.page_customer, text='Customer View')
        self.nb.add(self.page_staff, text='Staff Login / Dashboard')

        self.build_customer_page(self.page_customer)
        self.build_staff_page(self.page_staff)

    # -------------------- Customer Page --------------------
    def build_customer_page(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill='x', pady=(0,8))
        ttk.Label(top, text='Available Rooms', font=('Segoe UI', 12, 'bold')).pack(side='left')
        search_row = ttk.Frame(top)
        search_row.pack(side='right')
        self.search_var = tk.StringVar()
        ttk.Entry(search_row, textvariable=self.search_var, width=28).pack(side='left', padx=(0,8))
        ttk.Button(search_row, text='Search', command=self.load_rooms_customer, style='Secondary.TButton').pack(side='left', padx=4)
        ttk.Button(search_row, text='Refresh', command=self.load_rooms_customer).pack(side='left', padx=6)

        card = ttk.Frame(parent, padding=10, style='Card.TFrame')
        card.pack(fill='both', expand=True)

        columns = ('room_number','room_type','base_price','status')
        self.tv_customer = ttk.Treeview(card, columns=columns, show='headings', selectmode='browse', height=18)
        for c in columns:
            self.tv_customer.heading(c, text=c.replace('_',' ').title())
            if c == 'room_number':
                self.tv_customer.column(c, anchor='center', width=110)
            elif c == 'room_type':
                self.tv_customer.column(c, anchor='center', width=160)
            elif c == 'base_price':
                self.tv_customer.column(c, anchor='e', width=120)
            else:
                self.tv_customer.column(c, anchor='center', width=120)
        self.tv_customer.pack(fill='both', expand=True)
        self.tv_customer.bind('<Double-1>', lambda e: self.open_customer_room_card())

        self.tv_customer.tag_configure('vacant', background='#d9eefc')
        self.tv_customer.tag_configure('reserved', background='#eafae8')
        self.tv_customer.tag_configure('booked', background='#ffecec')

        self.load_rooms_customer()

    def load_rooms_customer(self):
        conn = get_connection()
        cursor = conn.cursor()
        query = 'SELECT room_number, room_type, base_price, status FROM rooms'
        search = self.search_var.get().strip()
        params = ()
        if search:
            query += ' WHERE room_number LIKE ? OR room_type LIKE ?'
            params = (f'%{search}%', f'%{search}%')
        query += ' ORDER BY room_number'
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        for r in self.tv_customer.get_children():
            self.tv_customer.delete(r)
        for row in rows:
            room_number, room_type, price, status = row
            price = decimal.Decimal(str(price))
            tag = ''
            if status and status.upper() == 'VACANT':
                tag = 'vacant'
            elif status and status.upper() == 'RESERVED':
                tag = 'reserved'
            elif status and status.upper() == 'BOOKED':
                tag = 'booked'
            self.tv_customer.insert('', 'end', values=(room_number, room_type, f"₱{price:.2f}", status), tags=(tag,))

    def open_customer_room_card(self):
        sel = self.tv_customer.selection()
        if not sel:
            return
        values = self.tv_customer.item(sel[0], 'values')
        room_number, room_type, price, status = values
        win = tk.Toplevel(self)
        win.title(f'Room {room_number}')
        win.geometry('420x220')
        frame = ttk.Frame(win, padding=12, style='Card.TFrame')
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text=f'Room {room_number}', font=('Segoe UI', 14, 'bold')).pack(anchor='w', pady=(0,6))
        ttk.Label(frame, text=f'Type: {room_type}').pack(anchor='w', pady=2)
        if '₱' not in price:
             ttk.Label(frame, text=f'Price: ₱{price}').pack(anchor='w', pady=2)
        else:
             ttk.Label(frame, text=f'Price: {price}').pack(anchor='w', pady=2)
        ttk.Label(frame, text=f'Status: {status}').pack(anchor='w', pady=2)
        ttk.Button(frame, text='Close', command=win.destroy, style='Secondary.TButton').pack(pady=10)

    # -------------------- Staff Page --------------------
    def build_staff_page(self, parent):
        self.login_panel = ttk.Frame(parent, padding=12)
        self.login_panel.pack(fill='x')
        ttk.Label(self.login_panel, text='Staff Login', font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        form = ttk.Frame(self.login_panel)
        form.pack(pady=8)
        ttk.Label(form, text='Username:').grid(row=0, column=0, sticky='e', padx=6, pady=4)
        self.entry_username = ttk.Entry(form, width=28)
        self.entry_username.grid(row=0, column=1, pady=4)
        ttk.Label(form, text='Password:').grid(row=1, column=0, sticky='e', padx=6, pady=4)
        self.entry_password = ttk.Entry(form, show='*', width=28)
        self.entry_password.grid(row=1, column=1, pady=4)
        btns = ttk.Frame(self.login_panel)
        btns.pack(pady=6)
        ttk.Button(btns, text='Login', command=self.handle_login, style='Primary.TButton').pack(side='left', padx=6)
        ttk.Button(btns, text='Register', command=self.handle_register, style='Secondary.TButton').pack(side='left')

        self.dashboard_area = ttk.Frame(parent, padding=8)

    def handle_register(self):
        full = simpledialog.askstring('Full name', 'Enter your full name:', parent=self)
        if not full:
            return
        username = simpledialog.askstring('Username', 'Choose a username:', parent=self)
        if not username:
            return
        password = simpledialog.askstring('Password', 'Choose a password:', parent=self)
        if not password:
            return
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO staff_users (full_name, username, password) VALUES (?,?,?)', (full, username, password))
            conn.commit()
            messagebox.showinfo('Registered', 'Staff registered successfully')
        except sqlite3.Error as e:
            messagebox.showerror('Error', f'Could not register: {e}')
        finally:
            cursor.close()
            conn.close()

    def handle_login(self):
        username = self.entry_username.get().strip()
        password = self.entry_password.get().strip()
        if not username or not password:
            messagebox.showwarning('Missing', 'Enter username and password')
            return
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT full_name FROM staff_users WHERE username=? AND password=?', (username, password))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row:
            self.current_staff = row[0]
            self.status_var.set(f'Logged in: {self.current_staff}')
            self.login_panel.forget()
            self.show_dashboard()
        else:
            messagebox.showerror('Login Failed', 'Invalid credentials')

    def show_dashboard(self):
        self.dashboard_area.pack(fill='both', expand=True)
        for child in self.dashboard_area.winfo_children():
            child.destroy()
        top = ttk.Frame(self.dashboard_area)
        top.pack(fill='x', pady=(0,8))
        ttk.Label(top, text=f'Staff: {self.current_staff}', font=('Segoe UI', 11, 'bold')).pack(side='left')
        ttk.Button(top, text='Logout', command=self.do_logout, style='Secondary.TButton').pack(side='right')

        main = ttk.Frame(self.dashboard_area)
        main.pack(fill='both', expand=True)

        left = ttk.Frame(main)
        left.pack(side='left', fill='both', expand=True, padx=(0,8))
        search_row = ttk.Frame(left)
        search_row.pack(fill='x', pady=(0,6))
        ttk.Label(search_row, text='Search:').pack(side='left')
        self.staff_search = tk.StringVar()
        ttk.Entry(search_row, textvariable=self.staff_search, width=28).pack(side='left', padx=6)
        ttk.Button(search_row, text='Go', command=self.load_rooms_staff, style='Secondary.TButton').pack(side='left')
        ttk.Button(search_row, text='Clear', command=self._clear_staff_search).pack(side='left', padx=6)

        card = ttk.Frame(left, style='Card.TFrame', padding=8)
        card.pack(fill='both', expand=True)
        columns = ('room_number','room_type','base_price','status')
        self.tv_rooms = ttk.Treeview(card, columns=columns, show='headings', selectmode='browse', height=18)
        for c in columns:
            self.tv_rooms.heading(c, text=c.replace('_',' ').title())
            if c == 'room_number':
                self.tv_rooms.column(c, anchor='center', width=110)
            elif c == 'room_type':
                self.tv_rooms.column(c, anchor='center', width=160)
            elif c == 'base_price':
                self.tv_rooms.column(c, anchor='e', width=120)
            else:
                self.tv_rooms.column(c, anchor='center', width=120)
        self.tv_rooms.pack(fill='both', expand=True)
        self.tv_rooms.bind('<Double-1>', lambda e: self.open_room_actions())

        self.tv_rooms.tag_configure('vacant', background='#d9eefc')
        self.tv_rooms.tag_configure('reserved', background='#eafae8')
        self.tv_rooms.tag_configure('booked', background='#ffecec')

        self.load_rooms_staff()
        right_container = ttk.Frame(main, width=360)
        right_container.pack(side='right', fill='y')
        right_container.pack_propagate(False)

        canvas = tk.Canvas(right_container, borderwidth=0, highlightthickness=0, bg='#f7fbff')
        scrollbar = ttk.Scrollbar(right_container, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        inner_frame = ttk.Frame(canvas, style='Card.TFrame', padding=12)
        canvas_window = canvas.create_window((0,0), window=inner_frame, anchor='nw')

        def _on_frame_config(event):
            canvas.configure(scrollregion=canvas.bbox('all'))
        inner_frame.bind('<Configure>', _on_frame_config)

        def _on_canvas_config(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind('<Configure>', _on_canvas_config)

        def _bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            canvas.bind_all("<Button-4>", _on_mousewheel)
            canvas.bind_all("<Button-5>", _on_mousewheel)
        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        def _on_mousewheel(event):
            if hasattr(event, 'delta'):
                canvas.yview_scroll(int(-1*(event.delta/120)), 'units')
            else:
                if event.num == 4:
                    canvas.yview_scroll(-3, 'units')
                elif event.num == 5:
                    canvas.yview_scroll(3, 'units')

        inner_frame.bind("<Enter>", _bind_mousewheel)
        inner_frame.bind("<Leave>", _unbind_mousewheel)

        ttk.Button(inner_frame, text='Add Room', command=self.add_room, style='Primary.TButton').pack(fill='x', pady=6)
        ttk.Button(inner_frame, text='Update Room', command=self.update_room, style='Secondary.TButton').pack(fill='x', pady=6)
        ttk.Button(inner_frame, text='Delete Room', command=self.delete_room, style='Secondary.TButton').pack(fill='x', pady=6)
        ttk.Separator(inner_frame).pack(fill='x', pady=8)
        ttk.Button(inner_frame, text='Set Reserved', command=lambda: self.prompt_set_status('RESERVED'), style='Primary.TButton').pack(fill='x', pady=6)
        ttk.Button(inner_frame, text='Set Booked', command=lambda: self.prompt_set_status('BOOKED'), style='Primary.TButton').pack(fill='x', pady=6)
        ttk.Button(inner_frame, text='Set Vacant', command=lambda: self.set_status('VACANT'), style='Secondary.TButton').pack(fill='x', pady=6)
        ttk.Separator(inner_frame).pack(fill='x', pady=8)
        ttk.Button(inner_frame, text='Damage Report', command=self.damage_report_window, style='Secondary.TButton').pack(fill='x', pady=6)
        ttk.Button(inner_frame, text='Checkout', command=self.checkout_window, style='Primary.TButton').pack(fill='x', pady=6)
        ttk.Separator(inner_frame).pack(fill='x', pady=8)
        ttk.Button(inner_frame, text='View Transactions', command=self.view_transactions, style='Secondary.TButton').pack(fill='x', pady=6)
        ttk.Button(inner_frame, text='Clear Transactions', command=self.clear_transactions, style='Secondary.TButton').pack(fill='x', pady=6)
        ttk.Frame(inner_frame, height=16, style='Card.TFrame').pack()

    def do_logout(self):
        self.current_staff = None
        self.status_var.set('Not logged in')
        self.dashboard_area.forget()
        self.login_panel.pack(fill='x')

    def _clear_staff_search(self):
        self.staff_search.set('')
        self.load_rooms_staff()

    def load_rooms_staff(self):
        conn = get_connection()
        cursor = conn.cursor()
        query = 'SELECT room_number, room_type, base_price, status FROM rooms'
        search = getattr(self, 'staff_search', tk.StringVar()).get().strip()
        params = ()
        if search:
            query += ' WHERE room_number LIKE ? OR room_type LIKE ?'
            params = (f'%{search}%', f'%{search}%')
        query += ' ORDER BY room_number'
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        for r in self.tv_rooms.get_children():
            self.tv_rooms.delete(r)
        for row in rows:
            room_number, room_type, price, status = row
            price = decimal.Decimal(str(price))
            tag = ''
            if status and status.upper() == 'VACANT':
                tag = 'vacant'
            elif status and status.upper() == 'RESERVED':
                tag = 'reserved'
            elif status and status.upper() == 'BOOKED':
                tag = 'booked'
            self.tv_rooms.insert('', 'end', values=(room_number, room_type, f"₱{price:.2f}", status), tags=(tag,))

    # -------------------- Room CRUD --------------------
    def add_room(self):
        dlg = AddRoomDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            room_number, room_type, prefix, price = dlg.result
            conn = get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute('INSERT INTO rooms (room_number, room_type, prefix, base_price, status, payment_status) VALUES (?,?,?,?,?,?)',
                               (room_number, room_type, prefix, float(price), 'VACANT', 'UNPAID'))
                conn.commit()
                messagebox.showinfo('Added', 'Room added')
                self.load_rooms_staff()
            except sqlite3.Error as e:
                messagebox.showerror('Error', f'Could not add room: {e}')
            finally:
                cursor.close(); conn.close()

    def update_room(self):
        sel = self.tv_rooms.selection()
        if not sel:
            messagebox.showwarning('Select', 'Select a room to update')
            return
        values = self.tv_rooms.item(sel[0], 'values')
        clean_price = values[2].replace('₱', '').replace(',', '')
        clean_values = (values[0], values[1], clean_price, values[3])
        
        dlg = AddRoomDialog(self, clean_values)
        self.wait_window(dlg)
        if dlg.result:
            room_number, room_type, prefix, price = dlg.result
            conn = get_connection(); cursor = conn.cursor()
            try:
                cursor.execute('UPDATE rooms SET room_type=?, prefix=?, base_price=? WHERE room_number=?',
                               (room_type, prefix, float(price), room_number))
                conn.commit()
                messagebox.showinfo('Updated', 'Room updated')
                self.load_rooms_staff()
            except sqlite3.Error as e:
                messagebox.showerror('Error', f'Could not update room: {e}')
            finally:
                cursor.close(); conn.close()

    def delete_room(self):
        sel = self.tv_rooms.selection()
        if not sel:
            messagebox.showwarning('Select', 'Select a room to delete')
            return
        values = self.tv_rooms.item(sel[0], 'values')
        room_number = values[0]
        if not messagebox.askyesno('Confirm', f'Delete room {room_number}?'):
            return
        conn = get_connection(); cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM rooms WHERE room_number=?', (room_number,))
            conn.commit()
            messagebox.showinfo('Deleted', 'Room deleted')
            self.load_rooms_staff()
        except sqlite3.Error as e:
            messagebox.showerror('Error', f'Could not delete room: {e}')
        finally:
            cursor.close(); conn.close()

    # -------------------- Status changes (with check-in & days) --------------------
    def prompt_set_status(self, new_status):
        sel = self.tv_rooms.selection()
        if not sel:
            messagebox.showwarning('Select', 'Select a room')
            return
        values = self.tv_rooms.item(sel[0], 'values')
        room_number = values[0]

        customer_name = simpledialog.askstring('Customer name', 'Enter customer name:', parent=self)
        if not customer_name:
            messagebox.showwarning('Missing', 'Customer name required')
            return

        default_ci = datetime.now().date().strftime('%Y-%m-%d')
        ci = simpledialog.askstring('Check-in date', f'Enter check-in date (YYYY-MM-DD):', initialvalue=default_ci, parent=self)
        if not ci:
            messagebox.showwarning('Missing', 'Check-in date required'); return
        try:
            checkin_date = datetime.strptime(ci.strip(), '%Y-%m-%d').date()
        except Exception:
            messagebox.showerror('Invalid', 'Check-in date must be YYYY-MM-DD'); return

        days = simpledialog.askinteger('Length of stay', 'Enter number of days the customer will stay:', initialvalue=1, minvalue=1, parent=self)
        if not days or days < 1:
            messagebox.showwarning('Missing', 'Number of days required'); return

        conn = get_connection(); cursor = conn.cursor()
        cursor.execute('SELECT base_price FROM rooms WHERE room_number=?', (room_number,))
        row = cursor.fetchone()
        cursor.close(); conn.close()
        base_price = decimal.Decimal(str(row[0])) if row and row[0] is not None else decimal.Decimal('0')
        stay_cost = (base_price * decimal.Decimal(days)).quantize(decimal.Decimal('0.01'))

        confirm_msg = f"Customer: {customer_name}\nRoom: {room_number}\nCheck-in: {checkin_date}\nDays: {days}\nStay cost: ₱{stay_cost:.2f}\n\nProceed to set {new_status}?"
        if not messagebox.askyesno('Confirm booking/reservation', confirm_msg):
            return
        checkout_date = checkin_date + timedelta(days=days)

        conn = get_connection(); cursor = conn.cursor()
        try:
            if new_status == 'BOOKED':
                cursor.execute('UPDATE rooms SET status=? WHERE room_number=?', (new_status, room_number))
                cursor.execute('INSERT INTO bookings (room_number, customer_name, checkin_date, checkout_date, prepaid, status) VALUES (?,?,?,?,?,?)',
                               (room_number, customer_name, checkin_date, checkout_date, 0.0, 'ACTIVE'))
                cursor.execute('INSERT INTO transactions (room_number, action, staff, customer_name, amount, notes, created_at) VALUES (?,?,?,?,?,?,?)',
                               (room_number, 'book', self.current_staff, customer_name, float(stay_cost), f'Booked for {days} days', datetime.now()))
                messagebox.showinfo('Booked', f'Room {room_number} booked. Stay cost recorded: ₱{stay_cost:.2f}')
            elif new_status == 'RESERVED':
                reserve_amount = (stay_cost * RESERVE_PERCENT).quantize(decimal.Decimal('0.01'))
                cursor.execute('UPDATE rooms SET status=? WHERE room_number=?', (new_status, room_number))
                cursor.execute('INSERT INTO bookings (room_number, customer_name, checkin_date, checkout_date, prepaid, status) VALUES (?,?,?,?,?,?)',
                               (room_number, customer_name, checkin_date, checkout_date, float(reserve_amount), 'ACTIVE'))
                cursor.execute('INSERT INTO transactions (room_number, action, staff, customer_name, amount, notes, created_at) VALUES (?,?,?,?,?,?,?)',
                               (room_number, 'reserve_charge', self.current_staff, customer_name, float(reserve_amount), f'Reserved (20%) for {days} days', datetime.now()))
                messagebox.showinfo('Reserved', f'Room {room_number} reserved. Reserve charge (20%): ₱{reserve_amount:.2f}')
            conn.commit()
            self.load_rooms_staff()
        except sqlite3.Error as e:
            messagebox.showerror('DB Error', f'Could not set reservation/booking: {e}')
        finally:
            cursor.close(); conn.close()

    def set_status(self, new_status, room_number=None):
        if not room_number:
            sel = self.tv_rooms.selection()
            if not sel:
                messagebox.showwarning('Select', 'Select a room')
                return
            room_number = self.tv_rooms.item(sel[0], 'values')[0]
        conn = get_connection()
        cursor = conn.cursor()
        try:
            if new_status == 'VACANT':
                cursor.execute('UPDATE rooms SET status=? WHERE room_number=?', ('VACANT', room_number))
                cursor.execute('INSERT INTO transactions (room_number, action, staff, customer_name, amount, notes, created_at) VALUES (?,?,?,?,?,?,?)',
                               (room_number, 'vacant', self.current_staff, None, 0.0, 'marked vacant / cancellation', datetime.now()))
            else:
                cursor.execute('UPDATE rooms SET status=? WHERE room_number=?', (new_status, room_number))
                cursor.execute('INSERT INTO transactions (room_number, action, staff, customer_name, amount, notes, created_at) VALUES (?,?,?,?,?,?,?)',
                               (room_number, new_status.lower(), self.current_staff, None, 0.0, f'set {new_status}', datetime.now()))
            conn.commit()
            self.load_rooms_staff()
            messagebox.showinfo('Status updated', f'Room {room_number} set to {new_status}')
        except sqlite3.Error as e:
            messagebox.showerror('DB Error', f'Could not set status: {e}')
        finally:
            cursor.close()
            conn.close()

    def open_room_actions(self):
        sel = self.tv_rooms.selection()
        if not sel:
            return
        values = self.tv_rooms.item(sel[0], 'values')
        room_number = values[0]
        action = simpledialog.askstring('Action', 'Enter action: reserve / book / vacant', parent=self)
        if not action:
            return
        action = action.strip().lower()
        if action in ('reserve', 'book'):
            if action == 'reserve':
                self.prompt_set_status('RESERVED')
            else:
                self.prompt_set_status('BOOKED')
        elif action == 'vacant':
            self.set_status('VACANT')
        else:
            messagebox.showinfo('Ignored', 'Unknown action')

    # -------------------- Transactions --------------------
    def view_transactions(self):
        win = tk.Toplevel(self)
        win.title('Transactions')
        win.geometry('1000x540')

        top = ttk.Frame(win, padding=8)
        top.pack(fill='x')

        ttk.Label(top, text='Search:').pack(side='left')
        search_var = tk.StringVar()
        ttk.Entry(top, textvariable=search_var, width=24).pack(side='left', padx=6)

        ttk.Label(top, text='Action:').pack(side='left', padx=(10,0))
        action_var = tk.StringVar()
        action_cb = ttk.Combobox(top, textvariable=action_var, state='readonly', width=18)
        action_cb['values'] = ('All','reserve_charge','book','vacant','damage_report','damage_removed','damage_cleared','checkout','booked','reserve')
        action_cb.set('All')
        action_cb.pack(side='left', padx=6)

        ttk.Label(top, text='Date from:').pack(side='left', padx=(10,0))
        date_from = tk.StringVar()
        ttk.Entry(top, textvariable=date_from, width=12).pack(side='left', padx=6)
        ttk.Label(top, text='to').pack(side='left')
        date_to = tk.StringVar()
        ttk.Entry(top, textvariable=date_to, width=12).pack(side='left', padx=6)

        def build_query():
            q = 'SELECT id, room_number, action, staff, customer_name, amount, notes, created_at FROM transactions'
            clauses = []
            params = []
            s = search_var.get().strip()
            if s:
                clauses.append("(room_number LIKE ? OR staff LIKE ? OR customer_name LIKE ? OR notes LIKE ?)")
                params.extend((f'%{s}%', f'%{s}%', f'%{s}%', f'%{s}%'))
            act = action_var.get()
            if act and act != 'All':
                clauses.append('action=?'); params.append(act)
            df = date_from.get().strip()
            dt = date_to.get().strip()
            if df:
                try:
                    datetime.strptime(df, '%Y-%m-%d')
                    clauses.append('created_at >= ?'); params.append(df + ' 00:00:00')
                except Exception:
                    messagebox.showwarning('Date format', 'Date from must be YYYY-MM-DD')
                    return None, None
            if dt:
                try:
                    datetime.strptime(dt, '%Y-%m-%d')
                    clauses.append('created_at <= ?'); params.append(dt + ' 23:59:59')
                except Exception:
                    messagebox.showwarning('Date format', 'Date to must be YYYY-MM-DD')
                    return None, None
            if clauses:
                q += ' WHERE ' + ' AND '.join(clauses)
            q += ' ORDER BY created_at DESC'
            return q, params

        btn_frame = ttk.Frame(top)
        btn_frame.pack(side='right')
        ttk.Button(btn_frame, text='Refresh', command=lambda: load_tx(), style='Secondary.TButton').pack(side='left', padx=6)
        ttk.Button(btn_frame, text='Export CSV', command=lambda: export_csv(), style='Secondary.TButton').pack(side='left', padx=6)
        ttk.Button(btn_frame, text='Clear All', command=lambda: clear_all(), style='Secondary.TButton').pack(side='left', padx=6)

        card = ttk.Frame(win, style='Card.TFrame', padding=8)
        card.pack(fill='both', expand=True, padx=8, pady=(6,8))

        columns = ('id','created_at','room','action','staff','customer','amount','notes')
        tv = ttk.Treeview(card, columns=columns, show='headings')
        headings = {
            'id':'ID', 'created_at':'Date/Time', 'room':'Room', 'action':'Action', 'staff':'Staff',
            'customer':'Customer', 'amount':'Amount', 'notes':'Notes'
        }
        for c in columns:
            tv.heading(c, text=headings[c])
            if c == 'notes':
                tv.column(c, width=320, anchor='w')
            elif c == 'amount':
                tv.column(c, width=110, anchor='e')
            elif c == 'created_at':
                tv.column(c, width=140, anchor='center')
            else:
                tv.column(c, width=100, anchor='center')
        tv.pack(fill='both', expand=True, side='left')

        vsb = ttk.Scrollbar(card, orient='vertical', command=tv.yview)
        vsb.pack(side='right', fill='y')
        tv.configure(yscrollcommand=vsb.set)

        footer = ttk.Frame(win, padding=8)
        footer.pack(fill='x')
        total_var = tk.StringVar(value='Total amount: ₱0.00')
        ttk.Label(footer, textvariable=total_var, font=('Segoe UI', 10, 'bold')).pack(side='left')

        def load_tx():
            q, params = build_query()
            if q is None:
                return
            for iid in tv.get_children():
                tv.delete(iid)
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(q, params)
            rows = cursor.fetchall()
            total = decimal.Decimal('0')
            for r in rows:
                try:
                    amt = decimal.Decimal(str(r[5] or 0))
                except Exception:
                    amt = decimal.Decimal('0')
                total += amt
                created = r[7]
                created_str = str(created)
                tv.insert('', 'end', values=(r[0], created_str, r[1], r[2], r[3] or '', r[4] or '', f"₱{amt:.2f}", r[6] or ''))
            cursor.close()
            conn.close()
            total_var.set(f'Total amount: ₱{total:.2f}')

        def export_csv():
            q, params = build_query()
            if q is None:
                return
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(q, params)
            rows = cursor.fetchall()
            if not rows:
                messagebox.showinfo('Export', 'No transactions to export')
                cursor.close()
                conn.close()
                return
            fpath = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV files','*.csv')], title='Save transactions as CSV')
            if not fpath:
                cursor.close()
                conn.close()
                return
            try:
                with open(fpath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['id','room_number','action','staff','customer_name','amount','notes','created_at'])
                    for r in rows:
                        writer.writerow(r)
                messagebox.showinfo('Export', f'Exported {len(rows)} transactions to {fpath}')
            except Exception as e:
                messagebox.showerror('Export Failed', f'Could not write file: {e}')
            finally:
                cursor.close()
                conn.close()

        def clear_all():
            if not messagebox.askyesno('Confirm', 'Clear ALL transactions? This cannot be undone.'):
                return
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM transactions')
            conn.commit()
            cursor.close()
            conn.close()
            load_tx()
            messagebox.showinfo('Cleared', 'All transactions cleared')

        menu = tk.Menu(win, tearoff=0)
        def on_view_details():
            sel = tv.selection()
            if not sel:
                return
            vals = tv.item(sel[0], 'values')
            tid = vals[0]
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id, room_number, action, staff, customer_name, amount, notes, created_at FROM transactions WHERE id=?', (tid,))
            rec = cursor.fetchone()
            cursor.close()
            conn.close()
            if not rec:
                messagebox.showerror('Not found', 'Transaction not found')
                return
            txt = (
                f"ID: {rec[0]}\n"
                f"Room: {rec[1]}\n"
                f"Action: {rec[2]}\n"
                f"Staff: {rec[3]}\n"
                f"Customer: {rec[4]}\n"
                f"Amount: ₱{rec[5]}\n"
                f"Notes: {rec[6]}\n"
                f"Date: {rec[7]}"
            )
            messagebox.showinfo('Transaction Details', txt)

        menu.add_command(label='View details', command=on_view_details)

        def on_right_click(event):
            rowid = tv.identify_row(event.y)
            if rowid:
                tv.selection_set(rowid)
                menu.post(event.x_root, event.y_root)

        tv.bind('<Button-3>', on_right_click)

        load_tx()

    # -------------------- Clear transactions --------------------
    def clear_transactions(self):
        if not messagebox.askyesno('Confirm', 'Clear all transactions?'):
            return
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM transactions')
        conn.commit()
        cursor.close()
        conn.close()
        messagebox.showinfo('Cleared', 'All transactions cleared')

    # -------------------- Damage Report --------------------
    def damage_report_window(self):
        sel = self.tv_rooms.selection()
        if not sel:
            messagebox.showwarning('Select', 'Select a room')
            return
        values = self.tv_rooms.item(sel[0], 'values')
        room_number = values[0]
        win = tk.Toplevel(self)
        win.title(f'Damage Report - Room {room_number}')
        win.geometry('720x480')
        header = ttk.Frame(win, padding=8); header.pack(fill='x')
        ttk.Label(header, text=f'Room {room_number} - Damage Report', font=('Segoe UI', 12, 'bold')).pack(side='left')
        frame = ttk.Frame(win, padding=10); frame.pack(fill='both', expand=True, padx=8, pady=8)

        tv = ttk.Treeview(frame, columns=('id','item','cost'), show='headings', selectmode='browse')
        tv.heading('id', text='ID'); tv.heading('item', text='Item'); tv.heading('cost', text='Cost')
        tv.column('id', width=60, anchor='center'); tv.column('item', anchor='w', width=380); tv.column('cost', width=120, anchor='e')
        tv.pack(fill='both', expand=True, pady=(0,8))

        PREMADE_ITEMS = {
            'Bed mattress': 2000.00, 'Bed frame': 1500.00, 'Wardrobe': 1200.00,
            'Chair': 300.00, 'Table': 500.00, 'TV': 4000.00, 'Aircon': 8000.00,
            'Lamp': 200.00, 'Curtain': 250.00, 'Door knob': 150.00, 'Window glass': 2500.00,
            'Plumbing (minor)': 800.00, 'Electrical (minor)': 700.00
        }

        controls = ttk.Frame(win, padding=8); controls.pack(fill='x', padx=8)
        ttk.Label(controls, text='Select item:').grid(row=0, column=0, sticky='e', padx=6, pady=4)
        item_cb = ttk.Combobox(controls, values=list(PREMADE_ITEMS.keys()) + ['Custom'], state='readonly', width=36)
        item_cb.set('Select item...'); item_cb.grid(row=0, column=1, sticky='we', padx=6)
        ttk.Label(controls, text='Cost:').grid(row=1, column=0, sticky='e', padx=6, pady=4)
        entry_cost = ttk.Entry(controls, width=20); entry_cost.grid(row=1, column=1, sticky='w', padx=6)
        ttk.Label(controls, text='Custom name:').grid(row=2, column=0, sticky='e', padx=6, pady=4)
        entry_custom = ttk.Entry(controls, width=36); entry_custom.grid(row=2, column=1, sticky='we', padx=6)
        entry_custom.configure(state='disabled')

        def on_item_change(event=None):
            sel_item = item_cb.get()
            if sel_item == 'Custom':
                entry_custom.configure(state='normal'); entry_custom.delete(0, 'end'); entry_cost.delete(0, 'end')
            elif sel_item == 'Select item...':
                entry_custom.configure(state='disabled'); entry_cost.delete(0, 'end')
            else:
                entry_custom.configure(state='disabled'); entry_custom.delete(0, 'end'); entry_cost.delete(0, 'end')
                entry_cost.insert(0, str(PREMADE_ITEMS.get(sel_item, '')))

        item_cb.bind('<<ComboboxSelected>>', on_item_change)

        def refresh_damages():
            for r in tv.get_children():
                tv.delete(r)
            conn = get_connection(); cursor = conn.cursor()
            cursor.execute('SELECT id, item_name, cost FROM damages WHERE room_number=? ORDER BY report_time DESC', (room_number,))
            for r in cursor.fetchall():
                tv.insert('', 'end', values=(r[0], r[1], f"₱{r[2]:.2f}"))
            cursor.close(); conn.close()

        def _get_active_booking_customer(room_no):
            conn2 = get_connection(); cur2 = conn2.cursor()
            try:
                cur2.execute('SELECT customer_name FROM bookings WHERE room_number=? AND status=? ORDER BY id DESC LIMIT 1', (room_no, 'ACTIVE'))
                b = cur2.fetchone()
                return b[0] if b and b[0] else None
            finally:
                cur2.close(); conn2.close()

        def add_damage():
            sel_item = item_cb.get()
            if sel_item == 'Select item...':
                messagebox.showwarning('Select', 'Choose an item or Custom')
                return
            if sel_item == 'Custom':
                item_name = entry_custom.get().strip()
                if not item_name:
                    messagebox.showwarning('Missing', 'Provide custom item name'); return
            else:
                item_name = sel_item
            cost = entry_cost.get().strip()
            if not cost:
                messagebox.showwarning('Missing', 'Provide cost'); return
            try:
                costv = decimal.Decimal(cost)
            except Exception:
                messagebox.showerror('Invalid', 'Cost invalid'); return

            customer_name_for_tx = _get_active_booking_customer(room_number)

            conn = get_connection(); cursor = conn.cursor()
            cursor.execute('INSERT INTO damages (room_number, item_name, cost, reported_by, report_time) VALUES (?,?,?,?,?)',
                           (room_number, item_name, float(costv), self.current_staff, datetime.now()))
            cursor.execute('INSERT INTO transactions (room_number, action, staff, customer_name, amount, notes, created_at) VALUES (?,?,?,?,?,?,?)',
                           (room_number, 'damage_report', self.current_staff, customer_name_for_tx, float(costv), f'Damage: {item_name}', datetime.now()))
            conn.commit(); cursor.close(); conn.close()
            item_cb.set('Select item...'); entry_cost.delete(0, 'end'); entry_custom.delete(0, 'end'); entry_custom.configure(state='disabled')
            refresh_damages()

        def remove_selected():
            sel_id = tv.selection()
            if not sel_id:
                messagebox.showwarning('Select', 'Select a damage item to remove'); return
            item = tv.item(sel_id[0], 'values')
            damage_id = item[0]
            if not messagebox.askyesno('Confirm', 'Remove selected damage entry?'):
                return
            customer_name_for_tx = _get_active_booking_customer(room_number)
            conn = get_connection(); cursor = conn.cursor()
            try:
                # SQLite uses ? placeholder
                cursor.execute('SELECT cost FROM damages WHERE id=?', (damage_id,))
                row = cursor.fetchone()
                cost_val = decimal.Decimal(str(row[0])) if row and row[0] is not None else decimal.Decimal('0')
                cursor.execute('DELETE FROM damages WHERE id=?', (damage_id,))
                cursor.execute('INSERT INTO transactions (room_number, action, staff, customer_name, amount, notes, created_at) VALUES (?,?,?,?,?,?,?)',
                               (room_number, 'damage_removed', self.current_staff, customer_name_for_tx, float(-cost_val), f'removed damage id {damage_id}', datetime.now()))
                conn.commit(); messagebox.showinfo('Removed', 'Damage entry removed')
            except sqlite3.Error as e:
                messagebox.showerror('Error', f'Could not remove damage: {e}')
            finally:
                cursor.close(); conn.close(); refresh_damages()

        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill='x', pady=6)
        ttk.Button(btn_frame, text='Add Damage', command=add_damage, style='Primary.TButton').pack(side='left', padx=6)
        ttk.Button(btn_frame, text='Remove Selected', command=remove_selected, style='Secondary.TButton').pack(side='left', padx=6)
        refresh_damages()

    # -------------------- Checkout --------------------
    def checkout_window(self):
        sel = self.tv_rooms.selection()
        if not sel:
            messagebox.showwarning('Select', 'Select a room')
            return
        values = self.tv_rooms.item(sel[0], 'values')
        room_number = values[0]
        raw_price_str = values[2].replace('₱','').replace(',','')
        price = decimal.Decimal(raw_price_str)
        
        conn = get_connection(); cursor = conn.cursor()

        cursor.execute('SELECT id, customer_name, checkin_date, checkout_date, prepaid FROM bookings WHERE room_number=? AND status=? ORDER BY id DESC LIMIT 1', (room_number, 'ACTIVE'))
        booking = cursor.fetchone()
        cursor.execute('SELECT IFNULL(SUM(cost),0) FROM damages WHERE room_number=?', (room_number,))
        damages_sum = decimal.Decimal(str(cursor.fetchone()[0] or 0))
        cursor.close(); conn.close()

        win = tk.Toplevel(self)
        win.title(f'Checkout - Room {room_number}')
        win.geometry('540x520')
        frame = ttk.Frame(win, padding=12); frame.pack(fill='both', expand=True)
        ttk.Label(frame, text=f'Checkout — Room {room_number}', font=('Segoe UI', 13, 'bold')).pack(anchor='w', pady=(0,6))

        form = ttk.Frame(frame); form.pack(fill='x', pady=6)
        ttk.Label(form, text='Customer name:').grid(row=0, column=0, sticky='e', padx=6)
        customer_var = tk.StringVar(value=(booking[1] if booking else ''))
        ttk.Entry(form, textvariable=customer_var, width=36).grid(row=0, column=1, sticky='w', padx=6)

        ttk.Label(form, text='Check-in (YYYY-MM-DD):').grid(row=1, column=0, sticky='e', padx=6)
        default_ci = datetime.now().date().strftime('%Y-%m-%d')
        if booking and booking[2]:
             if isinstance(booking[2], str):
                 default_ci = booking[2].split()[0] 
             else:
                 default_ci = booking[2].strftime('%Y-%m-%d')
        checkin_var = tk.StringVar(value=default_ci)
        checkin_entry = ttk.Entry(form, textvariable=checkin_var, width=20)
        checkin_entry.grid(row=1, column=1, sticky='w', padx=6)

        ttk.Label(form, text='Check-out (YYYY-MM-DD):').grid(row=2, column=0, sticky='e', padx=6)
        checkout_default = ''
        if booking and booking[3]:
            if isinstance(booking[3], str):
                checkout_default = booking[3].split()[0]
            else:
                checkout_default = booking[3].strftime('%Y-%m-%d')
        else:
            try:
                ci_dt = datetime.strptime(checkin_var.get(), '%Y-%m-%d').date()
                checkout_default = (ci_dt + timedelta(days=1)).strftime('%Y-%m-%d')
            except Exception:
                checkout_default = ''
        checkout_var = tk.StringVar(value=checkout_default)
        checkout_entry = ttk.Entry(form, textvariable=checkout_var, width=20)
        checkout_entry.grid(row=2, column=1, sticky='w', padx=6)

        ttk.Label(form, text='Prepaid amount:').grid(row=3, column=0, sticky='e', padx=6)
        prepaid_var = tk.StringVar(value=(str(booking[4]) if booking else '0'))
        prepaid_entry = ttk.Entry(form, textvariable=prepaid_var, width=20)
        prepaid_entry.grid(row=3, column=1, sticky='w', padx=6)

        ttk.Label(form, text=f'Damage charges: ₱{damages_sum}').grid(row=4, column=0, columnspan=2, sticky='w', padx=6, pady=6)
        ttk.Label(form, text=f'Base price/day: ₱{price}').grid(row=5, column=0, columnspan=2, sticky='w', padx=6, pady=4)

        ttk.Label(form, text='Length (days):').grid(row=6, column=0, sticky='e', padx=6, pady=4)
        default_length = 1
        if booking and booking[2] and booking[3]:
            try:
                ci = booking[2]
                co = booking[3]
                if isinstance(ci, str):
                    ci = datetime.strptime(ci.split()[0], '%Y-%m-%d').date()
                if isinstance(co, str):
                    co = datetime.strptime(co.split()[0], '%Y-%m-%d').date()
                delta = (co - ci).days
                if delta > 0:
                    default_length = delta
            except Exception:
                default_length = 1

        length_var = tk.StringVar(value=str(default_length))
        def only_digits(P):
            return (P == "") or P.isdigit()
        vcmd = (self.register(only_digits), '%P')
        length_entry = ttk.Entry(form, textvariable=length_var, width=8, validate='key', validatecommand=vcmd)
        length_entry.grid(row=6, column=1, sticky='w', padx=6)

        total_var = tk.StringVar(value='0')

        def compute_total():
            try:
                base = decimal.Decimal(str(price))
            except Exception as e:
                messagebox.showerror('Error', f'Invalid base price: {e}')
                return None

            days = None
            try:
                ci_text = checkin_var.get().strip()
                co_text = checkout_var.get().strip()
                if ci_text and co_text:
                    try:
                        ci = datetime.strptime(ci_text, '%Y-%m-%d').date()
                        co = datetime.strptime(co_text, '%Y-%m-%d').date()
                        delta_days = (co - ci).days
                        if delta_days > 0:
                            days = delta_days
                    except Exception:
                        days = None
            except Exception:
                days = None

            if days is None:
                lv = length_var.get().strip()
                if lv == '':
                    days = 1
                else:
                    try:
                        days = int(lv)
                        if days <= 0:
                            days = 1
                    except Exception:
                        messagebox.showwarning('Invalid', 'Length must be a positive integer; using 1')
                        days = 1

            try:
                length_var.set(str(int(days)))
            except Exception:
                pass

            try:
                stay = (base * decimal.Decimal(days)).quantize(decimal.Decimal('0.01'))
            except Exception as e:
                messagebox.showerror('Error', f'Error computing stay cost: {e}')
                return None

            try:
                damages = decimal.Decimal(damages_sum or 0).quantize(decimal.Decimal('0.01'))
            except Exception:
                damages = decimal.Decimal('0.00')

            try:
                prepaid_val = decimal.Decimal(prepaid_var.get() or 0).quantize(decimal.Decimal('0.01'))
            except Exception:
                messagebox.showwarning('Invalid', 'Prepaid amount is invalid; using 0')
                prepaid_val = decimal.Decimal('0.00')

            total = (stay + damages - prepaid_val).quantize(decimal.Decimal('0.01'))
            if total < 0:
                total = decimal.Decimal('0.00')

            total_var.set(f"₱{total:.2f}")
            return {'total': total, 'days': days, 'stay': stay, 'damages': damages, 'prepaid': prepaid_val}

        ttk.Button(form, text='Recalculate', command=compute_total, style='Secondary.TButton').grid(row=7, column=0, columnspan=2, pady=10)
        ttk.Label(form, text='Total:').grid(row=8, column=0, sticky='e', padx=6)
        ttk.Label(form, textvariable=total_var, font=('Segoe UI', 11, 'bold')).grid(row=8, column=1, sticky='w')

        try:
            compute_total()
        except Exception:
            pass

        def do_checkout():
            calc = compute_total()
            if calc is None:
                return
            total = calc['total']
            days = calc['days']

            conn = get_connection(); cursor = conn.cursor()
            try:
                cursor.execute('SELECT id, customer_name FROM bookings WHERE room_number=? AND status=? ORDER BY id DESC LIMIT 1', (room_number, 'ACTIVE'))
                b = cursor.fetchone()
                booking_id = None
                booking_customer = None
                if b:
                    booking_id = b[0]
                    booking_customer = b[1] or ''
                    try:
                        ci = datetime.strptime(checkin_var.get().strip(), '%Y-%m-%d').date()
                        new_co = ci + timedelta(days=days)
                    except Exception:
                        try:
                            new_co = datetime.strptime(checkout_var.get().strip(), '%Y-%m-%d').date()
                        except Exception:
                            new_co = None
                    if new_co:
                        cursor.execute('UPDATE bookings SET checkout_date=?, prepaid=?, status=? WHERE id=?',
                                       (new_co, float(prepaid_var.get() or 0), 'INACTIVE', booking_id))
                    else:
                        cursor.execute('UPDATE bookings SET prepaid=?, status=? WHERE id=?',
                                       (float(prepaid_var.get() or 0), 'INACTIVE', booking_id))

                cursor.execute('UPDATE rooms SET status=? WHERE room_number=?', ('VACANT', room_number))

                cursor.execute('INSERT INTO transactions (room_number, action, staff, customer_name, amount, notes, created_at) VALUES (?,?,?,?,?,?,?)',
                               (room_number, 'checkout', self.current_staff, customer_var.get(), float(total), f'checkout total {total}', datetime.now()))

                cursor.execute('SELECT COUNT(*), IFNULL(SUM(cost),0) FROM damages WHERE room_number=?', (room_number,))
                row = cursor.fetchone()
                damaged_count = int(row[0] or 0)
                damaged_sum = decimal.Decimal(str(row[1] or 0))

                if damaged_count > 0:
                    cursor.execute('DELETE FROM damages WHERE room_number=?', (room_number,))
                    cursor.execute('INSERT INTO transactions (room_number, action, staff, customer_name, amount, notes, created_at) VALUES (?,?,?,?,?,?,?)',
                                   (room_number, 'damage_cleared', self.current_staff, booking_customer, 0.0,
                                    f'Cleared {damaged_count} damage entries (sum {damaged_sum}) on checkout', datetime.now()))

                conn.commit()
                messagebox.showinfo('Checked out', f'Checked out. Total: ₱{total}')
                win.destroy()
                self.load_rooms_staff()
            except sqlite3.Error as e:
                messagebox.showerror('Error', f'Checkout failed: {e}')
            finally:
                cursor.close()
                conn.close()

        ttk.Button(form, text='Confirm Checkout', command=do_checkout, style='Primary.TButton').grid(row=9, column=0, columnspan=2, pady=12)

# -------------------- AddRoomDialog --------------------
class AddRoomDialog(tk.Toplevel):
    def __init__(self, parent, existing=None):
        super().__init__(parent)
        self.title('Room')
        self.resizable(False, False)
        self.result = None
        frame = ttk.Frame(self, padding=12, style='Card.TFrame'); frame.pack()
        ttk.Label(frame, text='Room number:').grid(row=0, column=0, sticky='e', padx=6, pady=6)
        self.entry_num = ttk.Entry(frame); self.entry_num.grid(row=0, column=1, padx=6, pady=6)
        ttk.Label(frame, text='Room type:').grid(row=1, column=0, sticky='e', padx=6, pady=6)
        self.entry_type = ttk.Entry(frame); self.entry_type.grid(row=1, column=1, padx=6, pady=6)
        ttk.Label(frame, text='Prefix:').grid(row=2, column=0, sticky='e', padx=6, pady=6)
        self.entry_prefix = ttk.Entry(frame); self.entry_prefix.grid(row=2, column=1, padx=6, pady=6)
        ttk.Label(frame, text='Base price:').grid(row=3, column=0, sticky='e', padx=6, pady=6)
        self.entry_price = ttk.Entry(frame); self.entry_price.grid(row=3, column=1, padx=6, pady=6)
        btns = ttk.Frame(frame); btns.grid(row=4, column=0, columnspan=2, pady=10)
        ttk.Button(btns, text='OK', command=self.on_ok, style='Primary.TButton').pack(side='left', padx=6)
        ttk.Button(btns, text='Cancel', command=self.destroy, style='Secondary.TButton').pack(side='left')
        if existing:
            try:
                self.entry_num.insert(0, existing[0])
                self.entry_type.insert(0, existing[1])
                self.entry_price.insert(0, existing[2])
                self.entry_prefix.insert(0, existing[1][:4].upper())
            except Exception:
                pass

    def on_ok(self):
        num = self.entry_num.get().strip()
        rtype = self.entry_type.get().strip()
        prefix = self.entry_prefix.get().strip() or (rtype[:4].upper() if rtype else '')
        price = self.entry_price.get().strip()
        if not num or not rtype or not price:
            messagebox.showwarning('Missing', 'Fill required fields'); return
        try:
            float(price)
        except:
            messagebox.showerror('Invalid', 'Price invalid'); return
        self.result = (num, rtype, prefix, price)
        self.destroy()

# -------------------- Entry Point --------------------
if __name__ == '__main__':
    try:
        app = HotelApp()
        app.mainloop()
    except Exception as e:
        try:
            messagebox.showerror('Fatal Error', f'An unexpected error occurred: {e}')
        except Exception:
            pass
        print('Fatal error:', e)
        sys.exit(1)