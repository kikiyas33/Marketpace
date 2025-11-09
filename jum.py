import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import sqlite3
import json
from datetime import datetime

# ==================== CONFIGURATION ====================
BOT_TOKEN = "8409251559:AAGkImxGAFVM5KDveKZKlCWZGAioSKzDjN4"  # Replace with your bot token from @BotFather
ADMIN_IDS = [5747226778]  # Replace with your Telegram user ID (get from @userinfobot)
CHANNEL_USERNAME = "jumarket"  # Your channel username

# ==================== DATABASE SETUP ====================
def init_db():
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            phone TEXT,
            is_admin BOOLEAN DEFAULT FALSE,
            joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Listings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_name TEXT,
            description TEXT,
            price REAL,
            category TEXT,
            photos TEXT,
            status TEXT DEFAULT 'pending',
            payment_method TEXT,
            payment_proof TEXT,
            admin_approved BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # User states table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_states (
            user_id INTEGER PRIMARY KEY,
            current_menu TEXT,
            previous_menu TEXT,
            temp_data TEXT,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Config table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Insert default config
    cursor.execute('''
        INSERT OR IGNORE INTO config (key, value) 
        VALUES ('telebirr_phone', '+251911234567'),
               ('listing_fee', '10'),
               ('telebirr_enabled', 'true'),
               ('manual_payments_enabled', 'true'),
               ('main_channel', 'UniversityMarketplace')
    ''')
    
    # Setup admin users
    for admin_id in ADMIN_IDS:
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, full_name, is_admin)
            VALUES (?, ?, ?, ?)
        ''', (admin_id, "admin", "Administrator", True))
    
    conn.commit()
    conn.close()

# ==================== STATE MANAGEMENT ====================
def get_user_state(user_id):
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_states WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'user_id': result[0],
            'current_menu': result[1],
            'previous_menu': result[2],
            'temp_data': json.loads(result[3]) if result[3] else {},
            'last_activity': result[4]
        }
    return None

def update_user_state(user_id, current_menu, previous_menu=None, temp_data=None):
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    
    if temp_data is None:
        temp_data = {}
    
    cursor.execute('''
        INSERT OR REPLACE INTO user_states 
        (user_id, current_menu, previous_menu, temp_data, last_activity)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, current_menu, previous_menu, json.dumps(temp_data), datetime.now()))
    
    conn.commit()
    conn.close()

# ==================== CONFIG MANAGEMENT ====================
def get_config(key):
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def set_config(key, value):
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

# ==================== USER MANAGEMENT ====================
def register_user(user_id, username, full_name):
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, full_name)
        VALUES (?, ?, ?)
    ''', (user_id, username, full_name))
    
    conn.commit()
    conn.close()

def is_user_admin(user_id):
    return user_id in ADMIN_IDS

def get_user_count():
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def get_user_phone(user_id):
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    cursor.execute("SELECT phone FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def update_user_phone(user_id, phone):
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET phone = ? WHERE user_id = ?", (phone, user_id))
    conn.commit()
    conn.close()
    # ==================== NAVIGATION SYSTEM ====================

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Show main menu to user"""
    # Check if user has completed registration
    user_phone = get_user_phone(user_id)
    has_phone = user_phone is not None
    
    keyboard = [
        [InlineKeyboardButton("🛍️ Sell Item", callback_data="sell_item")],
        [InlineKeyboardButton("🔍 Browse Listings", callback_data="browse_listings")],
        [InlineKeyboardButton("👤 My Profile", callback_data="my_profile")],
        [InlineKeyboardButton("📞 Support", callback_data="support")]
    ]
    
    # ONLY show admin button to actual admins
    if is_user_admin(user_id):
        keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = "🏠 **Main Menu**\n\nWelcome to University Marketplace!"
    
    if not has_phone:
        welcome_text += "\n\n⚠️ Please complete your registration in 'My Profile' to use all features."
    
    if update.callback_query:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    update_user_state(user_id, "main_menu", "welcome")

async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Show admin panel"""
    if not is_user_admin(user_id):
        await show_main_menu(update, context, user_id)
        return
    
    keyboard = [
        [InlineKeyboardButton("💰 Payment Management", callback_data="admin_payments")],
        [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 Channel Settings", callback_data="admin_channels")],
        [InlineKeyboardButton("👥 User Management", callback_data="admin_users")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back"), InlineKeyboardButton("🏠 Home", callback_data="home")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        "⚙️ **Admin Control Panel**\n\nManage your marketplace:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    update_user_state(user_id, "admin_panel", "main_menu")

async def show_payment_management(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Show payment management"""
    telebirr_status = "✅ Enabled" if get_config('telebirr_enabled') == 'true' else "❌ Disabled"
    manual_status = "✅ Enabled" if get_config('manual_payments_enabled') == 'true' else "❌ Disabled"
    
    keyboard = [
        [InlineKeyboardButton(f"Telebirr: {telebirr_status}", callback_data="toggle_telebirr")],
        [InlineKeyboardButton(f"Manual: {manual_status}", callback_data="toggle_manual")],
        [InlineKeyboardButton("📱 Change Telebirr Number", callback_data="change_telebirr_number")],
        [InlineKeyboardButton("💰 Set Listing Fee", callback_data="set_listing_fee")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back"), InlineKeyboardButton("🏠 Home", callback_data="home")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    status_text = f"""
💰 **Payment Management**

📱 Telebirr Number: {get_config('telebirr_phone')}
💰 Listing Fee: {get_config('listing_fee')} ETB

**Current Status:**
Telebirr Payments: {telebirr_status}
Manual Payments: {manual_status}
    """
    
    await update.callback_query.edit_message_text(
        status_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    update_user_state(user_id, "admin_payments", "admin_panel")

async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Show statistics dashboard"""
    total_users = get_user_count()
    total_listings = get_total_listings()
    pending_listings = get_pending_listings()
    listing_fee = get_config('listing_fee')
    
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh", callback_data="admin_stats")],
        [InlineKeyboardButton("📊 Detailed Analytics", callback_data="detailed_stats")],
        [InlineKeyboardButton("📄 Export Report", callback_data="export_stats")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back"), InlineKeyboardButton("🏠 Home", callback_data="home")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    stats_text = f"""
📊 **Marketplace Statistics - Live**

👥 **Users**
Total Users: {total_users}
Verified Users: {get_verified_users_count()}
Active Today: {get_active_users_count()}

💰 **Financial**
Total Revenue: {get_total_revenue()} ETB
Pending Payouts: {get_pending_revenue()} ETB
Listing Fee: {listing_fee} ETB

🛍️ **Listings**
Total Listings: {total_listings}
Pending Approval: {pending_listings}
Active Listings: {get_active_listings_count()}
Sold Items: {get_sold_listings_count()}

⚙️ **System**
Telebirr: {get_config('telebirr_enabled')}
Manual Payments: {get_config('manual_payments_enabled')}
    """
    
    await update.callback_query.edit_message_text(
        stats_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    update_user_state(user_id, "admin_stats", "admin_panel")

async def show_channel_management(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Show channel management"""
    current_channel = get_config('main_channel')
    
    keyboard = [
        [InlineKeyboardButton("🔄 Change Main Channel", callback_data="change_main_channel")],
        [InlineKeyboardButton("🔗 Test Channel Connection", callback_data="test_channel")],
        [InlineKeyboardButton("📊 Channel Stats", callback_data="channel_stats")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back"), InlineKeyboardButton("🏠 Home", callback_data="home")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    channel_text = f"""
📢 **Channel Management**

Current Main Channel: @{current_channel}
Channel Status: ✅ Connected

**Features:**
• Change main channel anytime
• Test channel connection
• View channel statistics
    """
    
    await update.callback_query.edit_message_text(
        channel_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    update_user_state(user_id, "admin_channels", "admin_panel")

async def show_user_management(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Show user management"""
    total_users = get_user_count()
    verified_users = get_verified_users_count()
    
    keyboard = [
        [InlineKeyboardButton("📋 View All Users", callback_data="view_all_users")],
        [InlineKeyboardButton("🔍 Search User", callback_data="search_user")],
        [InlineKeyboardButton("📤 Export User Data", callback_data="export_users")],
        [InlineKeyboardButton("👤 User Analytics", callback_data="user_analytics")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back"), InlineKeyboardButton("🏠 Home", callback_data="home")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    user_text = f"""
👥 **User Management**

Total Users: {total_users}
Verified Users: {verified_users}
Unverified Users: {total_users - verified_users}

**Actions:**
• View and manage all users
• Search specific users
• Export user data
• View user analytics
    """
    
    await update.callback_query.edit_message_text(
        user_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    update_user_state(user_id, "admin_users", "admin_panel")

async def show_broadcast_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Show broadcast menu"""
    total_users = get_user_count()
    
    keyboard = [
        [InlineKeyboardButton("📢 Broadcast to All", callback_data="broadcast_all")],
        [InlineKeyboardButton("👤 Broadcast to Sellers", callback_data="broadcast_sellers")],
        [InlineKeyboardButton("🛍️ Broadcast to Buyers", callback_data="broadcast_buyers")],
        [InlineKeyboardButton("📅 Schedule Broadcast", callback_data="schedule_broadcast")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back"), InlineKeyboardButton("🏠 Home", callback_data="home")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    broadcast_text = f"""
📢 **Broadcast Messages**

Total Recipients: {total_users} users

**Broadcast Types:**
• All Users ({total_users})
• Sellers Only
• Buyers Only
• Scheduled Messages

**Note:** You can send text, photos, and links.
    """
    
    await update.callback_query.edit_message_text(
        broadcast_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    update_user_state(user_id, "admin_broadcast", "admin_panel")
    # ==================== USER REGISTRATION SYSTEM ====================

async def start_user_registration(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Start user registration process"""
    user_phone = get_user_phone(user_id)
    
    if user_phone:
        # User already registered, show profile
        await show_user_profile(update, context, user_id)
        return
    
    keyboard = [
        [InlineKeyboardButton("📱 Share Phone Number", callback_data="share_phone")],
        [InlineKeyboardButton("✏️ Enter Manually", callback_data="enter_phone_manually")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back"), InlineKeyboardButton("🏠 Home", callback_data="home")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        "👤 **Complete Your Registration**\n\n"
        "To use our marketplace safely, we need your phone number for verification.\n\n"
        "Choose how to provide your phone number:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    update_user_state(user_id, "registration_phone", "main_menu", {"step": "phone"})

async def handle_phone_sharing(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Handle phone number sharing options"""
    if update.callback_query.data == "share_phone":
        # Ask user to share phone using Telegram's native button
        keyboard = [
            [InlineKeyboardButton("📱 Share My Phone", request_contact=True)],
            [InlineKeyboardButton("⬅️ Back", callback_data="back")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            "Please share your phone number using the button below:",
            reply_markup=reply_markup
        )
        
        update_user_state(user_id, "waiting_phone_share", "registration_phone")
    
    elif update.callback_query.data == "enter_phone_manually":
        await update.callback_query.edit_message_text(
            "Please enter your phone number:\n"
            "Format: +251911234567 or 0911234567\n\n"
            "Example: +251911234567",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="back")]
            ])
        )
        
        update_user_state(user_id, "waiting_phone_manual", "registration_phone")

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle received phone number from contact sharing"""
    user_id = update.effective_user.id
    
    if update.message.contact:
        phone_number = update.message.contact.phone_number
        # Save phone number to database
        update_user_phone(user_id, phone_number)
        
        await update.message.reply_text(
            f"✅ **Registration Completed!**\n\n"
            f"📱 Phone: {phone_number}\n"
            f"👤 Name: {update.effective_user.full_name}\n\n"
            "You can now use all marketplace features!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛍️ Start Selling", callback_data="sell_item")],
                [InlineKeyboardButton("🏠 Home", callback_data="home")]
            ]),
            parse_mode='Markdown'
        )
        
        update_user_state(user_id, "main_menu", "registration")

async def handle_manual_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle manually entered phone number"""
    user_id = update.effective_user.id
    phone_number = update.message.text
    
    # Basic phone validation
    if not any(char.isdigit() for char in phone_number):
        await update.message.reply_text(
            "❌ Invalid phone number. Please enter a valid phone number:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="back")]
            ])
        )
        return
    
    # Clean phone number
    phone_number = phone_number.replace(" ", "").replace("-", "")
    
    # Save phone number to database
    update_user_phone(user_id, phone_number)
    
    await update.message.reply_text(
        f"✅ **Registration Completed!**\n\n"
        f"📱 Phone: {phone_number}\n"
        f"👤 Name: {update.effective_user.full_name}\n\n"
        "You can now use all marketplace features!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛍️ Start Selling", callback_data="sell_item")],
            [InlineKeyboardButton("🏠 Home", callback_data="home")]
        ]),
        parse_mode='Markdown'
    )
    
    update_user_state(user_id, "main_menu", "registration")

async def show_user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Show user profile"""
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    cursor.execute("SELECT username, full_name, phone, joined_date FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data:
        username, full_name, phone, joined_date = user_data
        
        # Get user stats
        user_listings = get_user_listings_count(user_id)
        user_sales = get_user_sales_count(user_id)
        
        profile_text = f"""
👤 **Your Profile**

📛 Name: {full_name}
📱 Phone: {phone if phone else "Not provided"}
🆔 Username: @{username if username else 'None'}
📅 Member since: {joined_date[:10]}

📊 **Your Activity:**
🛍️ Listings Created: {user_listings}
✅ Successful Sales: {user_sales}
⭐ Rating: Calculating...

        """
        
        keyboard = [
            [InlineKeyboardButton("✏️ Edit Profile", callback_data="edit_profile")],
            [InlineKeyboardButton("📊 My Statistics", callback_data="my_stats")],
            [InlineKeyboardButton("🛍️ My Listings", callback_data="my_listings")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back"), InlineKeyboardButton("🏠 Home", callback_data="home")]
        ]
        
        if not phone:
            keyboard.insert(0, [InlineKeyboardButton("📱 Add Phone Number", callback_data="add_phone")])
        
    else:
        profile_text = "❌ User profile not found."
        keyboard = [[InlineKeyboardButton("🏠 Home", callback_data="home")]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        profile_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    update_user_state(user_id, "user_profile", "main_menu")

# ==================== STATISTICS HELPER FUNCTIONS ====================

def get_total_listings():
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM listings")
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def get_pending_listings():
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM listings WHERE status = 'pending'")
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def get_active_listings_count():
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM listings WHERE status = 'active'")
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def get_sold_listings_count():
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM listings WHERE status = 'sold'")
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def get_verified_users_count():
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE phone IS NOT NULL")
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def get_active_users_count():
    # Users active in last 24 hours
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM user_states WHERE last_activity > datetime('now', '-1 day')")
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def get_total_revenue():
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) * ? FROM listings WHERE admin_approved = 1", (get_config('listing_fee'),))
    result = cursor.fetchone()
    conn.close()
    return int(result[0]) if result else 0

def get_pending_revenue():
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) * ? FROM listings WHERE status = 'pending'", (get_config('listing_fee'),))
    result = cursor.fetchone()
    conn.close()
    return int(result[0]) if result else 0

def get_user_listings_count(user_id):
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM listings WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def get_user_sales_count(user_id):
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM listings WHERE user_id = ? AND status = 'sold'", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0
    # ==================== SELLING SYSTEM ====================

async def start_selling_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Start the selling process"""
    # Check if user has phone number (is registered)
    user_phone = get_user_phone(user_id)
    if not user_phone:
        await update.callback_query.edit_message_text(
            "❌ **Registration Required**\n\n"
            "Please complete your registration with phone number before selling items.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👤 Complete Registration", callback_data="my_profile")],
                [InlineKeyboardButton("🏠 Home", callback_data="home")]
            ]),
            parse_mode='Markdown'
        )
        return
    
    # Start selling process
    keyboard = [
        [InlineKeyboardButton("💻 Electronics", callback_data="cat_electronics")],
        [InlineKeyboardButton("📚 Textbooks", callback_data="cat_textbooks")],
        [InlineKeyboardButton("👕 Clothing", callback_data="cat_clothing")],
        [InlineKeyboardButton("🪑 Furniture", callback_data="cat_furniture")],
        [InlineKeyboardButton("📱 Phones", callback_data="cat_phones")],
        [InlineKeyboardButton("🔧 Other", callback_data="cat_other")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back"), InlineKeyboardButton("🏠 Home", callback_data="home")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        "🛍️ **Sell an Item**\n\n"
        "💰 Listing Fee: 10 ETB\n\n"
        "First, choose a category for your item:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    update_user_state(user_id, "selling_category", "main_menu", {"step": "category"})

async def handle_category_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Handle category selection"""
    category_map = {
        "cat_electronics": "Electronics",
        "cat_textbooks": "Textbooks", 
        "cat_clothing": "Clothing",
        "cat_furniture": "Furniture",
        "cat_phones": "Phones",
        "cat_other": "Other"
    }
    
    category = category_map.get(update.callback_query.data, "Other")
    
    # Store category in temp data
    user_state = get_user_state(user_id)
    temp_data = user_state.get('temp_data', {})
    temp_data['category'] = category
    temp_data['step'] = "item_name"
    
    update_user_state(user_id, "selling_item_name", "selling_category", temp_data)
    
    await update.callback_query.edit_message_text(
        f"📝 **Item Details**\n\n"
        f"Category: {category}\n\n"
        "Now, enter the name of your item:\n"
        "Example: 'MacBook Air M1 2020' or 'Calculus Textbook'",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="back")]
        ]),
        parse_mode='Markdown'
    )

async def handle_item_name(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Handle item name input"""
    item_name = update.message.text
    
    if len(item_name) < 3:
        await update.message.reply_text(
            "❌ Item name is too short. Please enter a descriptive name:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="back")]
            ])
        )
        return
    
    # Store item name in temp data
    user_state = get_user_state(user_id)
    temp_data = user_state.get('temp_data', {})
    temp_data['item_name'] = item_name
    temp_data['step'] = "description"
    
    update_user_state(user_id, "selling_description", "selling_item_name", temp_data)
    
    await update.message.reply_text(
        "📄 **Item Description**\n\n"
        "Now, describe your item in detail:\n"
        "• Condition (New/Used/Refurbished)\n"
        "• Specifications\n"
        "• Any defects or issues\n"
        "• Accessories included\n\n"
        "Example: 'Like new MacBook Air, used for 1 year, no scratches, comes with original charger'",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="back")]
        ]),
        parse_mode='Markdown'
    )

async def handle_item_description(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Handle item description input"""
    description = update.message.text
    
    if len(description) < 10:
        await update.message.reply_text(
            "❌ Description is too short. Please provide more details:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="back")]
            ])
        )
        return
    
    # Store description in temp data
    user_state = get_user_state(user_id)
    temp_data = user_state.get('temp_data', {})
    temp_data['description'] = description
    temp_data['step'] = "price"
    
    update_user_state(user_id, "selling_price", "selling_description", temp_data)
    
    await update.message.reply_text(
        "💰 **Set Price**\n\n"
        "Enter the price in ETB:\n"
        "Example: '1500' or '2500.50'\n\n"
        "💡 Tip: Research similar items for competitive pricing",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="back")]
        ]),
        parse_mode='Markdown'
    )

async def handle_item_price(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Handle item price input"""
    try:
        price = float(update.message.text)
        
        if price <= 0:
            await update.message.reply_text(
                "❌ Price must be greater than 0. Please enter a valid price:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back", callback_data="back")]
                ])
            )
            return
        
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid price. Please enter a number:\n"
            "Example: '1500' or '2500.50'",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="back")]
            ])
        )
        return
    
    # Store price in temp data
    user_state = get_user_state(user_id)
    temp_data = user_state.get('temp_data', {})
    temp_data['price'] = price
    temp_data['step'] = "photos"
    
    update_user_state(user_id, "selling_photos", "selling_price", temp_data)
    
    await update.message.reply_text(
        "📸 **Add Photos**\n\n"
        "Please send 1-3 photos of your item.\n"
        "Good photos help sell faster!\n\n"
        "Tips:\n"
        "• Take clear, well-lit photos\n"
        "• Show all angles\n"
        "• Include any defects\n"
        "• Show accessories included\n\n"
        "Send your photos now:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🚫 Skip Photos", callback_data="skip_photos")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back")]
        ]),
        parse_mode='Markdown'
    )

async def handle_item_photos(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Handle item photos"""
    if update.message.photo:
        # Store photo file IDs
        user_state = get_user_state(user_id)
        temp_data = user_state.get('temp_data', {})
        
        if 'photos' not in temp_data:
            temp_data['photos'] = []
        
        # Get the largest photo size
        photo = update.message.photo[-1]
        temp_data['photos'].append(photo.file_id)
        
        photo_count = len(temp_data['photos'])
        
        update_user_state(user_id, "selling_photos", "selling_price", temp_data)
        
        if photo_count < 3:
            await update.message.reply_text(
                f"✅ Photo {photo_count}/3 added. Send another photo or click 'Done with Photos':",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Done with Photos", callback_data="done_photos")],
                    [InlineKeyboardButton("🚫 No Photos", callback_data="skip_photos")],
                    [InlineKeyboardButton("⬅️ Back", callback_data="back")]
                ])
            )
        else:
            await update.message.reply_text(
                "✅ Maximum 3 photos reached. Click 'Done with Photos' to continue:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Done with Photos", callback_data="done_photos")],
                    [InlineKeyboardButton("⬅️ Back", callback_data="back")]
                ])
            )
    else:
        await update.message.reply_text(
            "❌ Please send photos of your item or click the buttons below:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Done with Photos", callback_data="done_photos")],
                [InlineKeyboardButton("🚫 No Photos", callback_data="skip_photos")],
                [InlineKeyboardButton("⬅️ Back", callback_data="back")]
            ])
        )

async def finalize_listing(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Finalize listing and show payment options"""
    user_state = get_user_state(user_id)
    temp_data = user_state.get('temp_data', {})
    
    # Create listing preview
    preview_text = f"""
🛍️ **Listing Preview**

📦 **Item:** {temp_data['item_name']}
📂 **Category:** {temp_data['category']}
💰 **Price:** {temp_data['price']} ETB
📄 **Description:** {temp_data['description']}
📸 **Photos:** {len(temp_data.get('photos', []))} added

💰 **Listing Fee:** 10 ETB

**Please choose payment method:**
    """
    
    # Check which payment methods are enabled
    keyboard = []
    
    if get_config('telebirr_enabled') == 'true':
        keyboard.append([InlineKeyboardButton("📱 Pay with Telebirr", callback_data="pay_telebirr")])
    
    if get_config('manual_payments_enabled') == 'true':
        keyboard.append([InlineKeyboardButton("💳 Manual Payment", callback_data="pay_manual")])
    
    keyboard.extend([
        [InlineKeyboardButton("✏️ Edit Listing", callback_data="edit_listing")],
        [InlineKeyboardButton("🗑️ Cancel", callback_data="cancel_listing")],
        [InlineKeyboardButton("🏠 Home", callback_data="home")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send preview with photos if available
    if temp_data.get('photos'):
        # Send first photo with caption
        await context.bot.send_photo(
            chat_id=user_id,
            photo=temp_data['photos'][0],
            caption=preview_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.callback_query.edit_message_text(
            preview_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    update_user_state(user_id, "selling_payment", "selling_photos", temp_data)

async def handle_payment_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Handle payment method selection"""
    payment_method = update.callback_query.data
    
    if payment_method == "pay_telebirr":
        await process_telebirr_payment(update, context, user_id)
    elif payment_method == "pay_manual":
        await process_manual_payment(update, context, user_id)
    elif payment_method == "edit_listing":
        await edit_listing(update, context, user_id)
    elif payment_method == "cancel_listing":
        await cancel_listing(update, context, user_id)

async def process_manual_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Process manual payment"""
    telebirr_phone = get_config('telebirr_phone')
    listing_fee = get_config('listing_fee')
    
    user_state = get_user_state(user_id)
    temp_data = user_state.get('temp_data', {})
    
    instructions = f"""
💳 **Manual Payment Instructions**

1. **Send {listing_fee} ETB** to our Telebirr account:
   📱 **{telebirr_phone}**

2. **Take a screenshot** of the payment confirmation

3. **Send the screenshot** here

4. We will verify and activate your listing within 1-2 hours

⚠️ **Important:**
• Include your username in payment note if possible
• Keep the screenshot until listing is approved
• Contact support if any issues
    """
    
    await update.callback_query.edit_message_text(
        instructions,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 I've Paid - Send Screenshot", callback_data="send_screenshot")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back"), InlineKeyboardButton("🏠 Home", callback_data="home")]
        ]),
        parse_mode='Markdown'
    )
    
    temp_data['payment_method'] = 'manual'
    update_user_state(user_id, "waiting_screenshot", "selling_payment", temp_data)

async def save_listing_to_database(user_id, temp_data, payment_method, payment_proof=None):
    """Save listing to database"""
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    
    photos_json = json.dumps(temp_data.get('photos', []))
    
    cursor.execute('''
        INSERT INTO listings 
        (user_id, item_name, description, price, category, photos, payment_method, payment_proof, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        temp_data['item_name'],
        temp_data['description'],
        temp_data['price'],
        temp_data['category'],
        photos_json,
        payment_method,
        payment_proof,
        'pending'
    ))
    
    listing_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return listing_id
    # ==================== PAYMENT PROCESSING ====================

async def process_telebirr_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Process Telebirr payment (placeholder for API integration)"""
    listing_fee = get_config('listing_fee')
    
    await update.callback_query.edit_message_text(
        f"📱 **Telebirr Payment**\n\n"
        f"💰 Amount: {listing_fee} ETB\n\n"
        "The Telebirr payment system is being integrated and will be available soon.\n\n"
        "For now, please use manual payment method.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Switch to Manual Payment", callback_data="pay_manual")],
            [InlineKeyboardButton("🏠 Home", callback_data="home")]
        ]),
        parse_mode='Markdown'
    )

async def handle_screenshot_submission(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Handle payment screenshot submission"""
    if update.message.photo:
        # Get the largest photo
        photo = update.message.photo[-1]
        file_id = photo.file_id
        
        # Get user and listing data
        user_state = get_user_state(user_id)
        temp_data = user_state.get('temp_data', {})
        
        # Save listing to database
        listing_id = save_listing_to_database(user_id, temp_data, 'manual', file_id)
        
        # Notify user
        await update.message.reply_text(
            "✅ **Payment Received!**\n\n"
            "Your listing has been submitted for admin approval.\n\n"
            "📋 **What happens next:**\n"
            "• Admin will verify your payment\n"
            "• Listing will be posted to channel\n"
            "• You'll be notified when approved\n\n"
            "⏰ Usually takes 1-2 hours",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛍️ Sell Another Item", callback_data="sell_item")],
                [InlineKeyboardButton("🏠 Home", callback_data="home")]
            ]),
            parse_mode='Markdown'
        )
        
        # Notify admins
        await notify_admins_listing_submitted(context, user_id, listing_id, temp_data, file_id)
        
        # Clear user state
        update_user_state(user_id, "main_menu", "waiting_screenshot")
        
    else:
        await update.message.reply_text(
            "❌ Please send a screenshot of your payment confirmation.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Send Screenshot", callback_data="send_screenshot")],
                [InlineKeyboardButton("🏠 Home", callback_data="home")]
            ])
        )

async def notify_admins_listing_submitted(context, user_id, listing_id, listing_data, screenshot_file_id):
    """Notify admins about new listing submission"""
    # Get user info
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    cursor.execute("SELECT username, full_name, phone FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    
    username, full_name, phone = user_data if user_data else ("Unknown", "Unknown", "Unknown")
    
    admin_message = f"""
🆕 **New Listing Submission**

📋 **Listing Details:**
🆔 ID: #{listing_id}
📦 Item: {listing_data['item_name']}
📂 Category: {listing_data['category']}
💰 Price: {listing_data['price']} ETB
📄 Description: {listing_data['description']}

👤 **Seller Info:**
📛 Name: {full_name}
📱 Phone: {phone}
🆔 Username: @{username if username else 'None'}
🆔 User ID: {user_id}

💰 **Payment Method:** Manual
    """
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{listing_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{listing_id}")
        ],
        [
            InlineKeyboardButton("📱 Contact Seller", callback_data=f"contact_{user_id}"),
            InlineKeyboardButton("👤 View Profile", callback_data=f"viewuser_{user_id}")
        ],
        [
            InlineKeyboardButton("📥 Download Screenshot", callback_data=f"download_{listing_id}"),
            InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_{listing_id}")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send to all admins
    for admin_id in ADMIN_IDS:
        try:
            # Send screenshot with admin controls
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=screenshot_file_id,
                caption=admin_message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        except Exception as e:
            logging.error(f"Failed to notify admin {admin_id}: {e}")
            # Send without photo if error
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_message + f"\n\n📸 Screenshot available for download",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

# ==================== ADMIN APPROVAL SYSTEM ====================

async def handle_admin_approval(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Handle admin approval/rejection of listings"""
    query = update.callback_query
    callback_data = query.data
    
    if callback_data.startswith('approve_'):
        listing_id = int(callback_data.replace('approve_', ''))
        await approve_listing(update, context, user_id, listing_id)
    
    elif callback_data.startswith('reject_'):
        listing_id = int(callback_data.replace('reject_', ''))
        await reject_listing(update, context, user_id, listing_id)
    
    elif callback_data.startswith('contact_'):
        seller_id = int(callback_data.replace('contact_', ''))
        await contact_seller(update, context, user_id, seller_id)
    
    elif callback_data.startswith('viewuser_'):
        seller_id = int(callback_data.replace('viewuser_', ''))
        await view_user_profile(update, context, user_id, seller_id)
    
    elif callback_data.startswith('download_'):
        listing_id = int(callback_data.replace('download_', ''))
        await download_screenshot(update, context, user_id, listing_id)
    
    elif callback_data.startswith('delete_'):
        listing_id = int(callback_data.replace('delete_', ''))
        await delete_listing(update, context, user_id, listing_id)

async def approve_listing(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id: int, listing_id: int):
    """Approve a listing and post to channel"""
    # Get listing details
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT l.*, u.username, u.phone 
        FROM listings l 
        JOIN users u ON l.user_id = u.user_id 
        WHERE l.id = ?
    ''', (listing_id,))
    listing_data = cursor.fetchone()
    
    if not listing_data:
        await update.callback_query.edit_message_text("❌ Listing not found.")
        return
    
    # Update listing status
    cursor.execute("UPDATE listings SET status = 'active', admin_approved = 1 WHERE id = ?", (listing_id,))
    conn.commit()
    conn.close()
    
    # Prepare channel post
    channel_post = create_channel_post(listing_data)
    channel_username = get_config('main_channel')
    
    try:
        # Post to channel
        if listing_data[6]:  # photos field
            photos = json.loads(listing_data[6])
            if photos:
                await context.bot.send_photo(
                    chat_id=f"@{channel_username}",
                    photo=photos[0],
                    caption=channel_post,
                    parse_mode='Markdown'
                )
            else:
                await context.bot.send_message(
                    chat_id=f"@{channel_username}",
                    text=channel_post,
                    parse_mode='Markdown'
                )
        else:
            await context.bot.send_message(
                chat_id=f"@{channel_username}",
                text=channel_post,
                parse_mode='Markdown'
            )
        
        # Notify seller
        seller_id = listing_data[1]  # user_id
        await context.bot.send_message(
            chat_id=seller_id,
            text=f"✅ **Your Listing is Live!**\n\n"
                 f"📦 **{listing_data[2]}**\n"
                 f"💰 **{listing_data[4]} ETB**\n\n"
                 f"Your item has been approved and posted to @{channel_username}\n"
                 f"Buyers can now contact you directly.",
            parse_mode='Markdown'
        )
        
        # Update admin message
        await update.callback_query.edit_message_text(
            f"✅ **Listing Approved!**\n\n"
            f"🆔 #{listing_id} - {listing_data[2]}\n"
            f"✅ Posted to @{channel_username}\n"
            f"✅ Seller notified",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Back to Admin", callback_data="admin_panel")],
                [InlineKeyboardButton("🏠 Home", callback_data="home")]
            ])
        )
        
    except Exception as e:
        logging.error(f"Failed to post to channel: {e}")
        await update.callback_query.edit_message_text(
            f"❌ **Failed to post to channel**\n\nError: {e}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Try Again", callback_data=f"approve_{listing_id}")],
                [InlineKeyboardButton("📊 Admin Panel", callback_data="admin_panel")]
            ])
        )

async def reject_listing(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id: int, listing_id: int):
    """Reject a listing"""
    # Get listing details
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, item_name FROM listings WHERE id = ?", (listing_id,))
    listing_data = cursor.fetchone()
    
    if not listing_data:
        await update.callback_query.edit_message_text("❌ Listing not found.")
        return
    
    seller_id, item_name = listing_data
    
    # Ask for rejection reason
    await update.callback_query.edit_message_text(
        f"❌ **Reject Listing**\n\n"
        f"Item: {item_name}\n"
        f"Please provide rejection reason:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🚫 Invalid Payment", callback_data=f"reject_reason_{listing_id}_invalid_payment")],
            [InlineKeyboardButton("📵 Poor Quality Photos", callback_data=f"reject_reason_{listing_id}_bad_photos")],
            [InlineKeyboardButton("📝 Incomplete Info", callback_data=f"reject_reason_{listing_id}_incomplete_info")],
            [InlineKeyboardButton("🔞 Prohibited Item", callback_data=f"reject_reason_{listing_id}_prohibited")],
            [InlineKeyboardButton("✏️ Custom Reason", callback_data=f"reject_custom_{listing_id}")],
            [InlineKeyboardButton("⬅️ Cancel", callback_data=f"view_listing_{listing_id}")]
        ])
    )

async def handle_rejection_reason(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id: int):
    """Handle rejection reason selection"""
    query = update.callback_query
    callback_data = query.data
    
    if callback_data.startswith('reject_reason_'):
        parts = callback_data.split('_')
        listing_id = int(parts[2])
        reason = ' '.join(parts[3:])
        await finalize_rejection(update, context, admin_id, listing_id, reason)
    
    elif callback_data.startswith('reject_custom_'):
        listing_id = int(callback_data.replace('reject_custom_', ''))
        await ask_custom_reason(update, context, admin_id, listing_id)

def create_channel_post(listing_data):
    """Create formatted channel post"""
    item_name = listing_data[2]  # item_name
    description = listing_data[3]  # description
    price = listing_data[4]  # price
    category = listing_data[5]  # category
    username = listing_data[8]  # username
    phone = listing_data[9]  # phone
    
    post = f"""
🛍️ **{item_name}** - {price} ETB

📂 Category: {category}
📄 Description: {description}

👤 **Seller:** @{username if username else 'Contact for info'}
📱 **Contact:** {phone}

#Marketplace #{"".join(category.split())}
    """
    
    return post

async def contact_seller(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id: int, seller_id: int):
    """Contact seller directly"""
    # Get seller info
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    cursor.execute("SELECT username, phone FROM users WHERE user_id = ?", (seller_id,))
    seller_data = cursor.fetchone()
    conn.close()
    
    if seller_data:
        username, phone = seller_data
        await update.callback_query.edit_message_text(
            f"👤 **Seller Contact Info**\n\n"
            f"🆔 User ID: {seller_id}\n"
            f"📛 Username: @{username if username else 'None'}\n"
            f"📱 Phone: {phone if phone else 'Not provided'}\n\n"
            f"Click below to contact:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📞 Call Phone", url=f"tel:{phone}")] if phone else [],
                [InlineKeyboardButton("💬 Message on Telegram", url=f"https://t.me/{username}")] if username else [],
                [InlineKeyboardButton("⬅️ Back", callback_data="back")]
            ])
        )
    else:
        await update.callback_query.edit_message_text("❌ Seller not found.")

async def view_user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id: int, user_id: int):
    """View user profile as admin"""
    conn = sqlite3.connect('marketplace.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.username, u.full_name, u.phone, u.joined_date,
               COUNT(l.id), SUM(CASE WHEN l.status = 'sold' THEN 1 ELSE 0 END)
        FROM users u 
        LEFT JOIN listings l ON u.user_id = l.user_id 
        WHERE u.user_id = ?
        GROUP BY u.user_id
    ''', (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data:
        username, full_name, phone, joined_date, total_listings, sold_listings = user_data
        
        profile_text = f"""
👤 **User Profile (Admin View)**

📛 Name: {full_name}
📱 Phone: {phone if phone else 'Not provided'}
🆔 Username: @{username if username else 'None'}
🆔 User ID: {user_id}
📅 Joined: {joined_date[:10]}

📊 **Activity:**
🛍️ Total Listings: {total_listings}
✅ Sold Items: {sold_listings}
⭐ Success Rate: {round((sold_listings/total_listings*100) if total_listings > 0 else 0, 1)}%
        """
        
        await update.callback_query.edit_message_text(
            profile_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📞 Contact", callback_data=f"contact_{user_id}")],
                [InlineKeyboardButton("🛍️ View Listings", callback_data=f"view_listings_{user_id}")],
                [InlineKeyboardButton("⬅️ Back", callback_data="back")]
            ]),
            parse_mode='Markdown'
        )
 # ==================== MESSAGE HANDLERS ====================

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages"""
    user_id = update.effective_user.id
    user_state = get_user_state(user_id)
    
    if not user_state:
        await show_main_menu(update, context, user_id)
        return
    
    current_menu = user_state['current_menu']
    
    if current_menu == "waiting_phone_manual":
        await handle_manual_phone(update, context)
    
    elif current_menu == "selling_item_name":
        await handle_item_name(update, context, user_id)
    
    elif current_menu == "selling_description":
        await handle_item_description(update, context, user_id)
    
    elif current_menu == "selling_price":
        await handle_item_price(update, context, user_id)
    
    elif current_menu == "waiting_screenshot":
        await handle_screenshot_submission(update, context, user_id)
    
    else:
        # Default fallback
        await show_main_menu(update, context, user_id)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main callback handler"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    callback_data = query.data
    
    try:
        # Navigation handlers
        if callback_data == "home":
            await show_main_menu(update, context, user_id)
            return
        
        elif callback_data == "back":
            user_state = get_user_state(user_id)
            if user_state and user_state['previous_menu']:
                await navigate_to_menu(update, context, user_id, user_state['previous_menu'])
            else:
                await show_main_menu(update, context, user_id)
            return
        
        # Main menu handlers
        elif callback_data == "sell_item":
            await start_selling_flow(update, context, user_id)
        
        elif callback_data == "browse_listings":
            await browse_listings(update, context, user_id)
        
        elif callback_data == "my_profile":
            await start_user_registration(update, context, user_id)
        
        elif callback_data == "support":
            await show_support(update, context, user_id)
        
        # Admin panel handlers
        elif callback_data == "admin_panel":
            await show_admin_panel(update, context, user_id)
        
        elif callback_data == "admin_payments":
            await show_payment_management(update, context, user_id)
        
        elif callback_data == "admin_stats":
            await show_statistics(update, context, user_id)
        
        elif callback_data == "admin_channels":
            await show_channel_management(update, context, user_id)
        
        elif callback_data == "admin_users":
            await show_user_management(update, context, user_id)
        
        elif callback_data == "admin_broadcast":
            await show_broadcast_menu(update, context, user_id)
        
        # Payment management handlers
        elif callback_data == "toggle_telebirr":
            current = get_config('telebirr_enabled')
            new_value = 'false' if current == 'true' else 'true'
            set_config('telebirr_enabled', new_value)
            await show_payment_management(update, context, user_id)
        
        elif callback_data == "toggle_manual":
            current = get_config('manual_payments_enabled')
            new_value = 'false' if current == 'true' else 'true'
            set_config('manual_payments_enabled', new_value)
            await show_payment_management(update, context, user_id)
        
        elif callback_data == "change_telebirr_number":
            await change_telebirr_number(update, context, user_id)
        
        elif callback_data == "set_listing_fee":
            await set_listing_fee(update, context, user_id)
        
        # User registration handlers
        elif callback_data == "share_phone":
            await handle_phone_sharing(update, context, user_id)
        
        elif callback_data == "enter_phone_manually":
            await handle_phone_sharing(update, context, user_id)
        
        elif callback_data == "add_phone":
            await start_user_registration(update, context, user_id)
        
        # Selling system handlers
        elif callback_data.startswith("cat_"):
            await handle_category_selection(update, context, user_id)
        
        elif callback_data == "skip_photos":
            user_state = get_user_state(user_id)
            temp_data = user_state.get('temp_data', {})
            temp_data['photos'] = []
            update_user_state(user_id, "selling_payment", "selling_photos", temp_data)
            await finalize_listing(update, context, user_id)
        
        elif callback_data == "done_photos":
            await finalize_listing(update, context, user_id)
        
        elif callback_data in ["pay_telebirr", "pay_manual", "edit_listing", "cancel_listing"]:
            await handle_payment_selection(update, context, user_id)
        
        elif callback_data == "send_screenshot":
            await update.callback_query.edit_message_text(
                "Please send the payment screenshot now:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back", callback_data="back")]
                ])
            )
        
        # Admin approval handlers
        elif (callback_data.startswith('approve_') or callback_data.startswith('reject_') or 
              callback_data.startswith('contact_') or callback_data.startswith('viewuser_') or
              callback_data.startswith('download_') or callback_data.startswith('delete_') or
              callback_data.startswith('reject_reason_') or callback_data.startswith('reject_custom_')):
            await handle_admin_approval(update, context, user_id)
        
        # Statistics and other handlers
        elif callback_data in ["detailed_stats", "export_stats", "view_all_users", 
                              "search_user", "export_users", "user_analytics",
                              "change_main_channel", "test_channel", "channel_stats",
                              "broadcast_all", "broadcast_sellers", "broadcast_buyers",
                              "schedule_broadcast", "edit_profile", "my_stats", "my_listings"]:
            await show_feature_coming_soon(update, context, user_id, callback_data)
        
        else:
            await query.edit_message_text("❌ Unknown command. Returning to main menu.")
            await show_main_menu(update, context, user_id)
    
    except Exception as e:
        logging.error(f"Error in callback handler: {e}")
        await query.edit_message_text("❌ An error occurred. Returning to main menu.")
        await show_main_menu(update, context, user_id)

async def navigate_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, menu_name: str):
    """Navigate to specific menu"""
    menu_handlers = {
        "main_menu": show_main_menu,
        "admin_panel": show_admin_panel,
        "admin_payments": show_payment_management,
        "admin_stats": show_statistics,
        "admin_channels": show_channel_management,
        "admin_users": show_user_management,
        "admin_broadcast": show_broadcast_menu,
        "user_profile": show_user_profile,
        "registration_phone": start_user_registration,
        "selling_category": start_selling_flow,
    }
    
    handler = menu_handlers.get(menu_name, show_main_menu)
    await handler(update, context, user_id)

# ==================== FEATURE PLACEHOLDERS ====================

async def browse_listings(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Browse active listings"""
    await update.callback_query.edit_message_text(
        "🔍 **Browse Listings**\n\n"
        "This feature will be available in the next update.\n"
        "You'll be able to view all active listings from the channel.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Visit Channel", url=f"https://t.me/{get_config('main_channel')}")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back"), InlineKeyboardButton("🏠 Home", callback_data="home")]
        ]),
        parse_mode='Markdown'
    )

async def show_support(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Show support information"""
    await update.callback_query.edit_message_text(
        "📞 **Support**\n\n"
        "Need help? Contact our support team:\n\n"
        "📧 Email: support@universitymarketplace.com\n"
        "📱 Telegram: @MarketplaceSupport\n"
        "🕒 Hours: 9AM - 6PM\n\n"
        "Common Issues:\n"
        "• Payment verification\n"
        "• Listing approval\n"
        "• Account issues\n"
        "• Technical problems",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Contact Support", url="https://t.me/MarketplaceSupport")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back"), InlineKeyboardButton("🏠 Home", callback_data="home")]
        ]),
        parse_mode='Markdown'
    )

async def change_telebirr_number(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Change Telebirr number"""
    await update.callback_query.edit_message_text(
        "📱 **Change Telebirr Number**\n\n"
        "This feature will be available in the next update.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="admin_payments"), InlineKeyboardButton("🏠 Home", callback_data="home")]
        ])
    )

async def set_listing_fee(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Set listing fee"""
    await update.callback_query.edit_message_text(
        "💰 **Set Listing Fee**\n\n"
        "This feature will be available in the next update.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="admin_payments"), InlineKeyboardButton("🏠 Home", callback_data="home")]
        ])
    )

async def show_feature_coming_soon(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, feature: str):
    """Show coming soon message for features"""
    feature_names = {
        "detailed_stats": "📊 Detailed Analytics",
        "export_stats": "📄 Export Report", 
        "view_all_users": "📋 View All Users",
        "search_user": "🔍 Search User",
        "export_users": "📤 Export User Data",
        "user_analytics": "👤 User Analytics",
        "change_main_channel": "🔄 Change Main Channel",
        "test_channel": "🔗 Test Channel Connection", 
        "channel_stats": "📊 Channel Stats",
        "broadcast_all": "📢 Broadcast to All",
        "broadcast_sellers": "👤 Broadcast to Sellers",
        "broadcast_buyers": "🛍️ Broadcast to Buyers",
        "schedule_broadcast": "📅 Schedule Broadcast",
        "edit_profile": "✏️ Edit Profile",
        "my_stats": "📊 My Statistics",
        "my_listings": "🛍️ My Listings"
    }
    
    feature_name = feature_names.get(feature, "This Feature")
    
    await update.callback_query.edit_message_text(
        f"{feature_name}\n\n🚧 **Coming Soon**\n\nThis feature is being developed and will be available in the next update!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="back"), InlineKeyboardButton("🏠 Home", callback_data="home")]
        ])
    )

async def edit_listing(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Edit listing before submission"""
    await update.callback_query.edit_message_text(
        "✏️ **Edit Listing**\n\n"
        "This feature will be available in the next update.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="back"), InlineKeyboardButton("🏠 Home", callback_data="home")]
        ])
    )

async def cancel_listing(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Cancel listing submission"""
    update_user_state(user_id, "main_menu", "selling_payment")
    await update.callback_query.edit_message_text(
        "🗑️ **Listing Cancelled**\n\nYour listing submission has been cancelled.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛍️ Start New Listing", callback_data="sell_item")],
            [InlineKeyboardButton("🏠 Home", callback_data="home")]
        ])
    )

async def download_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id: int, listing_id: int):
    """Download payment screenshot"""
    await update.callback_query.edit_message_text(
        "📥 **Download Screenshot**\n\n"
        "This feature will be available in the next update.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="back")]
        ])
    )

async def delete_listing(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id: int, listing_id: int):
    """Delete listing"""
    await update.callback_query.edit_message_text(
        "🗑️ **Delete Listing**\n\n"
        "This feature will be available in the next update.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="back")]
        ])
    )

async def ask_custom_reason(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id: int, listing_id: int):
    """Ask for custom rejection reason"""
    await update.callback_query.edit_message_text(
        "✏️ **Custom Rejection Reason**\n\n"
        "This feature will be available in the next update.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="back")]
        ])
    )

async def finalize_rejection(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id: int, listing_id: int, reason: str):
    """Finalize listing rejection"""
    await update.callback_query.edit_message_text(
        f"❌ **Listing Rejected**\n\n"
        f"Reason: {reason}\n\n"
        f"This feature will be fully implemented in the next update.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Admin Panel", callback_data="admin_panel")],
            [InlineKeyboardButton("🏠 Home", callback_data="home")]
        ])
    )

# ==================== START COMMAND ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    full_name = update.effective_user.full_name
    
    # Register user if not exists
    register_user(user_id, username, full_name)
    
    welcome_text = """
🎓 **Welcome to University Marketplace!**

Buy and sell items within your university community:

🛍️ **Sell Items:** List your items with photos
💰 **Safe Payments:** Secure payment system  
✅ **Verified Users:** All sellers are verified
📢 **Instant Posting:** Items posted to channel

Get started by completing your registration!
    """
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👤 Complete Registration", callback_data="my_profile")],
            [InlineKeyboardButton("🛍️ Start Selling", callback_data="sell_item")],
            [InlineKeyboardButton("🔍 Browse Listings", callback_data="browse_listings")]
        ]),
        parse_mode='Markdown'
    )
    
    update_user_state(user_id, "main_menu", "welcome")

# ==================== MAIN APPLICATION ====================

def main():
    """Main application function"""
    # Initialize database
    init_db()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))
    application.add_handler(MessageHandler(filters.PHOTO, handle_item_photos))
    
    # Start bot
    print("🤖 Marketplace Bot is starting...")
    print(f"👤 Admin IDs: {ADMIN_IDS}")
    print(f"📢 Channel: @{get_config('main_channel')}")
    print("💾 Database initialized successfully")
    print("🚀 Bot is now running...")
    
    application.run_polling()

if __name__ == "__main__":
    main()
    