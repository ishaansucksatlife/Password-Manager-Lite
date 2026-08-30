import mysql.connector
import csv
import json
import random
import os

def clear_screen():
    os.system('cls')

try:
    with open("config.json") as f:
        config = json.load(f)
except FileNotFoundError:
    print("ERROR: config.json not found. Run setup.bat first.")
    exit(1)

DB_HOST = config["host"]
DB_USER = config["user"]
DB_PASSWORD = config["password"]
DB_NAME = config["database"]

class DatabaseManager:
    def __init__(self):
        self.conn = None
        self.cursor = None

    def connect(self):
        try:
            self.conn = mysql.connector.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME
            )
            self.cursor = self.conn.cursor(dictionary=True, buffered=True)
            return True
        except mysql.connector.Error as e:
            print("Database error:", e)
            return False

    def close(self):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def execute(self, query, params=None):
        try:
            self.cursor.execute(query, params or ())
            self.conn.commit()
            return self.cursor
        except mysql.connector.Error as e:
            print("Query error:", e)
            return None

    def fetch_one(self, query, params=None):
        rows = self.fetch_all(query, params)
        if rows:
            return rows[0]
        return None

    def fetch_all(self, query, params=None):
        self.execute(query, params)
        return self.cursor.fetchall() if self.cursor else []

    def get_master(self):
        return self.fetch_one("SELECT * FROM master WHERE id = 1")

    def set_master(self, password, pin=None, trusted_until=None):
        self.execute(
            "INSERT INTO master (id, master_password, pin, trusted_until) VALUES (1, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE master_password=%s, pin=%s, trusted_until=%s",
            (password, pin, trusted_until, password, pin, trusted_until)
        )

class Stack:
    def __init__(self):
        self.items = []

    def push(self, item):
        self.items.append(item)

    def pop(self):
        if not self.is_empty():
            return self.items.pop()
        return None

    def is_empty(self):
        return len(self.items) == 0

def encrypt(text, shift=3):
    result = ""
    for c in text:
        if c.isalpha():
            base = ord('A') if c.isupper() else ord('a')
            result += chr((ord(c) - base + shift) % 26 + base)
        else:
            result += c
    return result

def decrypt(text, shift=3):
    return encrypt(text, -shift)

def generate_password(length=12):
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
    result = ""
    for i in range(length):
        result += chars[random.randint(0, len(chars) - 1)]
    return result

def check_strength(password):
    score = 0
    if len(password) >= 8:
        score += 1
    if len(password) >= 12:
        score += 1
    for c in password:
        if 'a' <= c <= 'z':
            score += 1
            break
    for c in password:
        if 'A' <= c <= 'Z':
            score += 1
            break
    for c in password:
        if '0' <= c <= '9':
            score += 1
            break
    for c in password:
        if c in "!@#$%^&*":
            score += 1
            break
    return score

class VaultService:
    def __init__(self, db):
        self.db = db
        self.logged_in = False
        self.master_password = None
        self.undo_stack = Stack()

    def create_vault(self, password):
        self.db.set_master(password)
        self.logged_in = True
        self.master_password = password
        return True

    def login_with_master(self, password):
        config = self.db.get_master()
        if config and config['master_password'] == password:
            self.logged_in = True
            self.master_password = password
            return True
        return False

    def login_with_pin(self):
        config = self.db.get_master()
        if not config or not config['pin']:
            return False
        pin = input("Enter PIN: ").strip()
        if pin == config['pin']:
            self.logged_in = True
            return True
        print("Invalid PIN.")
        return False

    def set_pin(self):
        config = self.db.get_master()
        if not config:
            print("No vault exists. Create one first.")
            return False
        pin = input("Create PIN (minimum 4 digits): ").strip()
        if len(pin) < 4 or not pin.isdigit():
            print("PIN must be at least 4 digits.")
            return False
        self.db.set_master(config['master_password'], pin, "30_days")
        print("PIN set successfully.")
        return True

    def remove_pin(self):
        config = self.db.get_master()
        if not config:
            print("No vault exists.")
            return False
        if not config['pin']:
            print("No PIN is currently set.")
            return False
        confirm = input("Remove PIN? This will disable PIN unlock. (y/n): ").lower()
        if confirm == 'y':
            self.db.set_master(config['master_password'], None, None)
            print("PIN removed.")
            return True
        else:
            print("Cancelled.")
            return False

    def change_master_password(self, old, new, confirm):
        if new != confirm:
            print("New passwords do not match.")
            return False
        config = self.db.get_master()
        if not config or config['master_password'] != old:
            print("Current master password is incorrect.")
            return False
        self.db.set_master(new, config['pin'], config['trusted_until'])
        self.master_password = new
        print("Master password changed successfully.")
        return True

    def verify_pin(self, pin):
        config = self.db.get_master()
        if config and config['pin']:
            return pin == config['pin']
        return False

    def add_entry(self, service, username, password, notes="", favorite=0):
        if not self.logged_in:
            print("Not logged in.")
            return False
        try:
            encrypted_password = encrypt(password)
            self.db.execute(
                "INSERT INTO entries (service, username, password, notes, is_favorite) VALUES (%s, %s, %s, %s, %s)",
                (service, username, encrypted_password, notes, favorite)
            )
            self.undo_stack.push(('add', service, username, password))
            return True
        except Exception as e:
            print("Error adding entry:", e)
            return False

    def get_password(self, service, username=None):
        if not self.logged_in:
            print("Not logged in.")
            return None
        try:
            if username:
                row = self.db.fetch_one("SELECT * FROM entries WHERE service=%s AND username=%s", (service, username))
            else:
                row = self.db.fetch_one("SELECT * FROM entries WHERE service=%s", (service,))
            if row:
                decrypted_password = decrypt(row['password'])
                return dict(row), decrypted_password
            return None
        except Exception as e:
            print("Error retrieving password:", e)
            return None

    def get_entry_by_id(self, entry_id):
        if not self.logged_in:
            return None
        try:
            row = self.db.fetch_one("SELECT * FROM entries WHERE id=%s", (entry_id,))
            if row:
                decrypted_password = decrypt(row['password'])
                return dict(row), decrypted_password
            return None
        except Exception as e:
            print("Error retrieving entry:", e)
            return None

    def list_entries(self, favorites_only=False):
        if not self.logged_in:
            print("Not logged in.")
            return []
        try:
            if favorites_only:
                rows = self.db.fetch_all("SELECT * FROM entries WHERE is_favorite=1")
            else:
                rows = self.db.fetch_all("SELECT * FROM entries")
            rows.sort(key=lambda x: x['service'].lower())
            return rows
        except Exception as e:
            print("Error listing entries:", e)
            return []

    def update_entry_by_id(self, entry_id, new_service, new_username, new_password, notes, favorite):
        if not self.logged_in:
            return False
        try:
            row = self.db.fetch_one("SELECT * FROM entries WHERE id=%s", (entry_id,))
            if not row:
                print("Entry not found.")
                return False
            print("Old values:")
            print(f"  Service: {row['service']}")
            print(f"  Username: {row['username']}")
            print("New values:")
            print(f"  Service: {new_service}")
            print(f"  Username: {new_username}")
            confirm = input("Confirm update? (y/n): ").lower()
            if confirm != 'y':
                print("Update cancelled.")
                return False

            self.undo_stack.push(('update', row['service'], row['username'], row['password']))
            encrypted_password = encrypt(new_password)
            self.db.execute(
                "UPDATE entries SET service=%s, username=%s, password=%s, notes=%s, is_favorite=%s WHERE id=%s",
                (new_service, new_username, encrypted_password, notes, favorite, entry_id)
            )
            return True
        except Exception as e:
            print("Error updating entry:", e)
            return False

    def toggle_favorite_by_id(self, entry_id):
        if not self.logged_in:
            return False
        try:
            row = self.db.fetch_one("SELECT * FROM entries WHERE id=%s", (entry_id,))
            if not row:
                print("Entry not found.")
                return False
            new_fav = 1 if row['is_favorite'] == 0 else 0
            self.db.execute(
                "UPDATE entries SET is_favorite=%s WHERE id=%s",
                (new_fav, entry_id)
            )
            if new_fav:
                print("Added to favorites.")
            else:
                print("Removed from favorites.")
            return True
        except Exception as e:
            print("Error toggling favorite:", e)
            return False

    def delete_entry_by_id(self, entry_id):
        if not self.logged_in:
            return False
        try:
            row = self.db.fetch_one("SELECT * FROM entries WHERE id=%s", (entry_id,))
            if row:
                self.undo_stack.push(('delete', row['service'], row['username'], row['password']))
            self.db.execute("DELETE FROM entries WHERE id=%s", (entry_id,))
            return True
        except Exception as e:
            print("Error deleting entry:", e)
            return False

    def delete_by_pattern(self, pattern):
        if not self.logged_in:
            return False
        try:
            items = self.db.fetch_all("SELECT * FROM entries WHERE service LIKE %s OR username LIKE %s", (pattern, pattern))
            if not items:
                print("No matching entries found.")
                return False
            for item in items:
                self.delete_entry_by_id(item['id'])
            print(f"Deleted {len(items)} entries.")
            return True
        except Exception as e:
            print("Error in batch delete:", e)
            return False

    def reset_vault(self, master_password):
        config = self.db.get_master()
        if not config or config['master_password'] != master_password:
            print("Incorrect master password.")
            return False
        confirm = input("This will DELETE ALL entries from your vault. Type 'DELETE' to confirm: ").strip()
        if confirm != 'DELETE':
            print("Reset cancelled.")
            return False
        try:
            self.db.execute("DELETE FROM entries")
            while not self.undo_stack.is_empty():
                self.undo_stack.pop()
            print("Vault has been reset. All entries deleted.")
            return True
        except Exception as e:
            print("Error resetting vault:", e)
            return False

    def undo_last_action(self):
        action = self.undo_stack.pop()
        if not action:
            print("Nothing to undo.")
            return
        op, service, username, password = action
        if op == 'add':
            self.db.execute("DELETE FROM entries WHERE service=%s AND username=%s", (service, username))
            print("Undo: Deleted", service, username)
        elif op == 'delete':
            self.db.execute(
                "INSERT INTO entries (service, username, password) VALUES (%s, %s, %s)",
                (service, username, password)
            )
            print("Undo: Restored", service, username)
        elif op == 'update':
            self.db.execute(
                "UPDATE entries SET password=%s WHERE service=%s AND username=%s",
                (password, service, username)
            )
            print("Undo: Reverted update for", service, username)

    def health_check(self):
        items = self.list_entries()
        return {"total": len(items)}

def export_to_csv(vault, filename='export.csv'):
    items = vault.list_entries()
    try:
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['service', 'username', 'password', 'notes', 'is_favorite'])
            for item in items:
                _, decrypted_password = vault.get_password(item['service'], item['username'])
                writer.writerow([item['service'], item['username'], decrypted_password, item.get('notes', ''), item.get('is_favorite', 0)])
        return filename
    except Exception as e:
        print("Export error:", e)
        return None

def import_from_csv(vault, filename):
    count = 0
    try:
        with open(filename, 'r') as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                if len(row) >= 3:
                    service, username, password = row[0], row[1], row[2]
                    notes = row[3] if len(row) > 3 else ''
                    fav = int(row[4]) if len(row) > 4 else 0
                    vault.add_entry(service, username, password, notes, fav)
                    count += 1
        return count
    except FileNotFoundError:
        print("File not found.")
        return 0
    except Exception as e:
        print("Import error:", e)
        return 0

def show_dashboard(health):
    print(f"Total entries: {health['total']}")

# --- Pagination helper ---
def paginated_display(items, title, page_size=10, show_numbers=True, allow_selection=True):
    """
    Displays items with page controls.
    Returns: selected entry (if allow_selection and user chooses a number) or None.
    """
    if not items:
        print("No entries found.")
        return None

    total = len(items)
    total_pages = (total + page_size - 1) // page_size
    current_page = 1

    while True:
        clear_screen()
        print(f"Main > {title}")
        print("-" * 30)
        start = (current_page - 1) * page_size
        end = min(start + page_size, total)
        page_items = items[start:end]

        print(f"Page {current_page}/{total_pages}  (Total: {total} entries)")
        print()
        if show_numbers:
            print("#\tService\t\tUsername\tFavorite")
            print("-" * 50)
            for idx, item in enumerate(page_items, start=start+1):
                fav = "Yes" if item['is_favorite'] else "No"
                print(f"{idx}\t{item['service']}\t\t{item['username']}\t\t{fav}")
        else:
            for item in page_items:
                print(f"  {item['service']} ({item['username']})")
        print()
        print("[n] Next page   [p] Previous page   [b] Back")
        if allow_selection:
            print("Enter a number to select that entry, or 0 to cancel.")
        choice = input("Choice: ").strip().lower()

        if choice == 'b':
            return None
        elif choice == 'n':
            if current_page < total_pages:
                current_page += 1
            else:
                print("Already on last page.")
                input("Press Enter to continue...")
        elif choice == 'p':
            if current_page > 1:
                current_page -= 1
            else:
                print("Already on first page.")
                input("Press Enter to continue...")
        elif allow_selection and choice.isdigit():
            num = int(choice)
            if num == 0:
                return None
            if 1 <= num <= total:
                return items[num-1]
            else:
                print("Invalid number.")
                input("Press Enter to continue...")
        else:
            print("Invalid choice.")
            input("Press Enter to continue...")

# --- Sub‑screens using pagination ---

def add_entry_screen(vault):
    clear_screen()
    print("Main > Add Entry")
    print("-" * 30)
    service = input("Service (or 'back' to cancel): ").strip()
    if service.lower() in ('back', 'cancel'):
        return
    username = input("Username (or 'back' to cancel): ").strip()
    if username.lower() in ('back', 'cancel'):
        return
    password = input("Password (or 'back' to cancel): ").strip()
    if password.lower() in ('back', 'cancel'):
        return
    notes = input("Notes (optional): ").strip()
    vault.add_entry(service, username, password, notes)
    print("Entry added.")
    input("\nPress Enter to continue...")

def retrieve_password_screen(vault):
    items = vault.list_entries()
    if not items:
        clear_screen()
        print("Main > Retrieve Password")
        print("-" * 30)
        print("No entries to retrieve.")
        input("\nPress Enter to continue...")
        return

    selected = paginated_display(items, "Retrieve Password", page_size=10, allow_selection=True)
    if selected is None:
        return

    # Verify PIN if set
    config = vault.db.get_master()
    if config and config['pin']:
        pin = input("Enter PIN to view password: ").strip()
        if not vault.verify_pin(pin):
            print("Incorrect PIN.")
            input("\nPress Enter to continue...")
            return

    result = vault.get_password(selected['service'], selected['username'])
    if result:
        _, decrypted_password = result
        print("Password:", decrypted_password)
        print("💡 Copy this password manually.")
    else:
        print("Error retrieving password.")
    input("\nPress Enter to continue...")

def list_entries_screen(vault, favorites_only=False):
    items = vault.list_entries(favorites_only)
    clear_screen()
    title = "List Favorites" if favorites_only else "List All Entries"
    paginated_display(items, title, page_size=10, allow_selection=False)
    input("\nPress Enter to continue...")

def delete_entry_screen(vault):
    items = vault.list_entries()
    if not items:
        clear_screen()
        print("Main > Delete Entry")
        print("-" * 30)
        print("No entries to delete.")
        input("\nPress Enter to continue...")
        return

    selected = paginated_display(items, "Delete Entry", page_size=10, allow_selection=True)
    if selected is None:
        return

    confirm = input(f"Delete {selected['service']} ({selected['username']})? (y/n): ").lower()
    if confirm == 'y':
        if vault.delete_entry_by_id(selected['id']):
            print("Entry deleted.")
        else:
            print("Failed to delete.")
    else:
        print("Cancelled.")
    input("\nPress Enter to continue...")

def search_entries_screen(vault):
    clear_screen()
    print("Main > Search Entries")
    print("-" * 30)
    search_term = input("Search term (or 'back' to cancel): ").strip().lower()
    if search_term in ('back', 'cancel'):
        return
    items = vault.list_entries()
    results = []
    for item in items:
        if search_term in item['service'].lower() or search_term in item['username'].lower():
            results.append(item)
    paginated_display(results, "Search Results", page_size=10, allow_selection=False)
    input("\nPress Enter to continue...")

def update_entry_screen(vault):
    items = vault.list_entries()
    if not items:
        clear_screen()
        print("Main > Update Entry")
        print("-" * 30)
        print("No entries to update.")
        input("\nPress Enter to continue...")
        return

    selected = paginated_display(items, "Update Entry", page_size=10, allow_selection=True)
    if selected is None:
        return

    print("Leave blank to keep current value.")
    new_service = input(f"New service ({selected['service']}): ").strip() or selected['service']
    new_username = input(f"New username ({selected['username']}): ").strip() or selected['username']
    new_password = input("New password (press Enter to keep): ")
    if not new_password:
        _, new_password = vault.get_password(selected['service'], selected['username'])
    new_notes = input(f"New notes ({selected['notes'] or ''}): ").strip() or selected['notes']
    favorite = input("Favorite? (y/n): ").lower() == 'y'

    if vault.update_entry_by_id(selected['id'], new_service, new_username, new_password, new_notes, 1 if favorite else 0):
        print("Entry updated.")
    else:
        print("Update failed.")
    input("\nPress Enter to continue...")

def toggle_favorite_screen(vault):
    items = vault.list_entries()
    if not items:
        clear_screen()
        print("Main > Toggle Favorite")
        print("-" * 30)
        print("No entries to toggle.")
        input("\nPress Enter to continue...")
        return

    selected = paginated_display(items, "Toggle Favorite", page_size=10, allow_selection=True)
    if selected is None:
        return

    if vault.toggle_favorite_by_id(selected['id']):
        print("Favorite toggled.")
    else:
        print("Failed to toggle.")
    input("\nPress Enter to continue...")

def generate_password_screen():
    clear_screen()
    print("Main > Generate Password")
    print("-" * 30)
    try:
        length_str = input("Password length (default 12, or 'back' to cancel): ").strip()
        if length_str.lower() in ('back', 'cancel'):
            return
        length = int(length_str) if length_str else 12
    except ValueError:
        length = 12
    generated_password = generate_password(length)
    print("Generated password:", generated_password)
    print("Strength score (0-6):", check_strength(generated_password))
    input("\nPress Enter to continue...")

def export_screen(vault):
    clear_screen()
    print("Main > Export to CSV")
    print("-" * 30)
    path = export_to_csv(vault)
    if path:
        print(f"Exported to {path}")
    input("\nPress Enter to continue...")

def import_screen(vault):
    clear_screen()
    print("Main > Import from CSV")
    print("-" * 30)
    path = input("CSV file path (or 'back' to cancel): ").strip()
    if path.lower() in ('back', 'cancel'):
        return
    if not path:
        path = 'import.csv'
    count = import_from_csv(vault, path)
    print(f"Imported {count} entries.")
    input("\nPress Enter to continue...")

def dashboard_screen(vault):
    clear_screen()
    print("Main > Health Dashboard")
    print("-" * 30)
    health = vault.health_check()
    show_dashboard(health)
    input("\nPress Enter to continue...")

def set_pin_screen(vault):
    clear_screen()
    print("Main > Set/Change PIN")
    print("-" * 30)
    vault.set_pin()
    input("\nPress Enter to continue...")

def remove_pin_screen(vault):
    clear_screen()
    print("Main > Remove PIN")
    print("-" * 30)
    vault.remove_pin()
    input("\nPress Enter to continue...")

def change_master_password_screen(vault):
    clear_screen()
    print("Main > Change Master Password")
    print("-" * 30)
    old = input("Enter current master password: ").strip()
    new = input("Enter new master password: ").strip()
    confirm = input("Confirm new master password: ").strip()
    vault.change_master_password(old, new, confirm)
    input("\nPress Enter to continue...")

def reset_vault_screen(vault):
    clear_screen()
    print("Main > Reset Vault")
    print("-" * 30)
    print("⚠️  This will delete ALL entries from your vault. Master password and PIN will remain.")
    master_pw = input("Enter your master password to confirm: ").strip()
    vault.reset_vault(master_pw)
    input("\nPress Enter to continue...")

def undo_screen(vault):
    clear_screen()
    print("Main > Undo Last Action")
    print("-" * 30)
    vault.undo_last_action()
    input("\nPress Enter to continue...")

def batch_delete_screen(vault):
    clear_screen()
    print("Main > Batch Delete")
    print("-" * 30)
    pattern = input("Pattern (e.g., 'google', or 'back' to cancel): ").strip()
    if pattern.lower() in ('back', 'cancel'):
        return
    if '%' not in pattern:
        pattern = '%' + pattern + '%'
    vault.delete_by_pattern(pattern)
    input("\nPress Enter to continue...")

def show_menu(vault):
    total = 0
    favorites = 0
    try:
        items = vault.list_entries()
        total = len(items)
        favorites = sum(1 for i in items if i['is_favorite'])
    except:
        pass

    print("\nPASSWORD MANAGER")
    print("=" * 30)
    if total > 0:
        print(f"📁 Total entries: {total}  |  ⭐ Favorites: {favorites}")
    else:
        print("📁 Vault is empty.")
    print("-" * 30)
    print("1. Add entry")
    print("2. Retrieve password")
    print("3. List all entries")
    print("4. List favorites only")
    print("5. Delete entry")
    print("6. Search entries")
    print("7. Update entry")
    print("8. Toggle favorite")
    print("9. Generate password")
    print("10. Export to CSV")
    print("11. Import from CSV")
    print("12. Health Dashboard")
    print("13. Set/Change PIN")
    print("14. Remove PIN")
    print("15. Change Master Password")
    print("16. Undo last action")
    print("17. Batch delete")
    print("18. Reset Vault (delete all entries)")
    print("19. Exit")
    print("=" * 30)
    return input("Choose (1-19): ")

def main():
    db = DatabaseManager()
    if not db.connect():
        print("Database connection failed.")
        return

    vault = VaultService(db)

    master = db.get_master()
    if not master:
        print("First-time setup.")
        master_password = input("Create Master Password: ")
        vault.create_vault(master_password)
        if input("Set PIN? (y/n): ").lower() == 'y':
            vault.set_pin()
    else:
        if master['pin']:
            if vault.login_with_pin():
                print("Unlocked with PIN.")
            else:
                for attempts in range(3):
                    master_password = input("Master Password: ")
                    if vault.login_with_master(master_password):
                        print("Login successful.")
                        break
                    print("Incorrect password.")
                else:
                    print("Too many failed attempts.")
                    return
        else:
            for attempts in range(3):
                master_password = input("Master Password: ")
                if vault.login_with_master(master_password):
                    print("Login successful.")
                    break
                print("Incorrect password.")
            else:
                print("Too many failed attempts.")
                return

    while True:
        clear_screen()
        choice = show_menu(vault)
        if choice == '1':
            add_entry_screen(vault)
        elif choice == '2':
            retrieve_password_screen(vault)
        elif choice == '3':
            list_entries_screen(vault, favorites_only=False)
        elif choice == '4':
            list_entries_screen(vault, favorites_only=True)
        elif choice == '5':
            delete_entry_screen(vault)
        elif choice == '6':
            search_entries_screen(vault)
        elif choice == '7':
            update_entry_screen(vault)
        elif choice == '8':
            toggle_favorite_screen(vault)
        elif choice == '9':
            generate_password_screen()
        elif choice == '10':
            export_screen(vault)
        elif choice == '11':
            import_screen(vault)
        elif choice == '12':
            dashboard_screen(vault)
        elif choice == '13':
            set_pin_screen(vault)
        elif choice == '14':
            remove_pin_screen(vault)
        elif choice == '15':
            change_master_password_screen(vault)
        elif choice == '16':
            undo_screen(vault)
        elif choice == '17':
            batch_delete_screen(vault)
        elif choice == '18':
            reset_vault_screen(vault)
        elif choice == '19':
            print("Goodbye!")
            break
        else:
            print("Invalid choice.")
            input("\nPress Enter to continue...")

    db.close()

if __name__ == "__main__":
    main()