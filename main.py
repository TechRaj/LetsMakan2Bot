import os
import telebot
import time
from threading import Timer
import sqlite3
import keep_alive

keep_alive.keep_alive()

my_secret = os.environ['API_KEY']
bot = telebot.TeleBot(my_secret)

timers = {}

help_message = (
    "Hi, welcome to LetsMakanBot! This bot simplifies food ordering in your group chat. "
    "Say goodbye to chat floods during meal planning!\n\n"
    "🔹 /help - Displays this help message with detailed command information.\n"
    "🔹 /startorder [time in mins] - Initiates a new order session. Use this to start collating orders. Optionally, set a timer (in minutes) to auto finalize orders. E.g., /startorder 15. The person who starts the order will be considered the purchaser.\n"
    "🔹 /addorder [your order] - Adds your order to the current session. E.g., /addorder Chicken Rice\n"
    "🔹 /editorder [your new order] - Modifies your most recent order. E.g., /editorder Nasi Lemak\n"
    "🔹 /removeorder - Removes your latest order from the current session.\n"
    "🔹 /vieworder - Views the current orders. Use this to check the order details.\n"
    "🔹 /cancelorder - Deletes all orders in the current session.\n"
    "🔹 /finalise - Finalises the current order session, providing a summary of all orders to the group and a detailed summary to the purchaser.\n"
    "🔹 /submitprice [order ID] [price] - (For Purchaser) After finalising, submit the price of each order. E.g., /submitprice 1 5.50\n"
    "🔹 /setpaylahlink [link] - (For Purchaser) Set your DBS PayLah! link for receiving payments. E.g., /setpaylahlink https://paylahlink\n\n"
    "📌 Note: The bot will not respond to messages that are not commands. Use the commands above to interact.\n\n"
    "If you have any feedback or need support, feel free to DM @TechRajX.\n\n"
    "Happy ordering! 😊"
)



def auto_finalize(chat_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT order_text FROM orders WHERE chat_id = ?", (chat_id,))
    orders = cursor.fetchall()
    if chat_id in timers:
        timers[chat_id].cancel()
        del timers[chat_id]

    if orders:
        order_summary = "\n".join(order[0] for order in orders)
        bot.send_message(chat_id, f"Order session automatically finalized. Summary:\n{order_summary}")

        # Clear orders after finalizing
        cursor.execute("DELETE FROM orders WHERE chat_id = ?", (chat_id,))
        cursor.execute("UPDATE order_sessions SET active = 0 WHERE chat_id = ?", (chat_id,))
        conn.commit()

    conn.close()


# DB Handlers

def initialize_database():
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_sessions (
            chat_id INTEGER PRIMARY KEY,
            active INTEGER
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_id INTEGER,
            order_text TEXT,
            FOREIGN KEY (chat_id) REFERENCES order_sessions(chat_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT
        );
    ''')

    conn.commit()
    conn.close()



initialize_database()


def get_db_connection():
    conn = sqlite3.connect('orders.db')
    return conn

def add_order_to_db(chat_id, user_id, order_text):
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO orders (chat_id, user_id, order_text) VALUES (?, ?, ?)", 
                   (chat_id, user_id, order_text))
    conn.commit()
    conn.close()

def get_orders_from_db(chat_id):
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute("SELECT order_text FROM orders WHERE chat_id=?", (chat_id,))
    orders = cursor.fetchall()
    conn.close()
    return orders

def delete_orders_from_db(chat_id):
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM orders WHERE chat_id=?", (chat_id,))
    conn.commit()
    conn.close()

def is_active_session(chat_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT active FROM order_sessions WHERE chat_id = ?", (chat_id,))
    result = cursor.fetchone()
    conn.close()

    # Check if the result exists and the session is active (active == 1)
    return result is not None and result[0] == 1

def upgrade_database_with_purchaser():
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()

    # Check if the 'purchaser_id' column already exists
    cursor.execute("PRAGMA table_info(order_sessions)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'purchaser_id' not in columns:
        cursor.execute('''
            ALTER TABLE order_sessions
            ADD COLUMN purchaser_id INTEGER;
        ''')
        conn.commit()

    conn.close()

upgrade_database_with_purchaser()


def upgrade_database_with_price():
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()

    # Check if the 'price' column already exists in the 'orders' table
    cursor.execute("PRAGMA table_info(orders)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'price' not in columns:
        cursor.execute('''
            ALTER TABLE orders
            ADD COLUMN price REAL DEFAULT NULL;
        ''')
        conn.commit()

    conn.close()

upgrade_database_with_price()


def add_paylah_link_column():
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()

    # Check if the 'paylah_link' column already exists in the 'order_sessions' table
    cursor.execute("PRAGMA table_info(order_sessions)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'paylah_link' not in columns:
        cursor.execute('''
            ALTER TABLE order_sessions
            ADD COLUMN paylah_link TEXT;
        ''')
        conn.commit()

    conn.close()

add_paylah_link_column()

def add_status_column_to_orders():
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()

    # Check if the 'status' column already exists in the 'orders' table
    cursor.execute("PRAGMA table_info(orders)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'status' not in columns:
        cursor.execute('''
            ALTER TABLE orders
            ADD COLUMN status TEXT DEFAULT 'pending';
        ''')
        conn.commit()

    conn.close()
    
add_status_column_to_orders()

def add_status_column_to_order_sessions():
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(order_sessions)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'status' not in columns:
        cursor.execute('''
            ALTER TABLE order_sessions
            ADD COLUMN status TEXT DEFAULT 'active';
        ''')
        conn.commit()

    conn.close()

add_status_column_to_order_sessions()

def create_user_paylah_table():
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_paylah_links (
            user_id INTEGER PRIMARY KEY,
            paylah_link TEXT
        );
    ''')
    conn.commit()
    conn.close()

create_user_paylah_table()


# Message Handlers

@bot.message_handler(commands=['startorder'])
def start_order(message):
    chat_id = message.chat.id
    purchaser_id = message.from_user.id
    args = message.text.split()
    timeout_duration = 30  # Default timeout duration in minutes

    if len(args) > 1 and args[1].isdigit():
        timeout_duration = int(args[1])

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if a session already exists for the chat_id
    cursor.execute("SELECT active, status FROM order_sessions WHERE chat_id = ?", (chat_id,))
    session = cursor.fetchone()

    if session:
        # If session exists and is not finalised, warn the user
        if session[0] == 1 and session[1] != 'finalised':
            bot.send_message(chat_id, "An order session is already active. Use /finalise to end it, or /cancelorder to delete it.")
            conn.close()
            return
        # If session exists but is finalised, reset it for a new order
        else:
            cursor.execute("UPDATE order_sessions SET active = 1, purchaser_id = ?, status = 'active' WHERE chat_id = ?", (purchaser_id, chat_id))
    else:
        # If no session exists, create a new one
        cursor.execute("INSERT INTO order_sessions (chat_id, active, purchaser_id, status) VALUES (?, 1, ?, 'active')", (chat_id, purchaser_id))

    # Start a timer for automatic finalization
    if chat_id in timers:
        timers[chat_id].cancel()
    timer = Timer(timeout_duration * 60, auto_finalize, [chat_id])
    timer.start()
    timers[chat_id] = timer

    bot.send_message(chat_id, f"The order session has started! Add your orders with /addorder. This session will auto-finalize in {timeout_duration} minutes.")

    conn.commit()
    conn.close()




@bot.message_handler(commands=['addorder'])
def add_order(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    first_name = message.from_user.first_name  # or username if preferable
    order_text = message.text[len('/addorder '):].strip()

    if not is_active_session(chat_id):
        bot.send_message(chat_id, "No active order session. Start a new session with /startorder.")
        return

    if not order_text:
        bot.send_message(chat_id, "Please add your order after the command. E.g., /addorder Nasi Lemak")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (user_id, first_name) VALUES (?, ?)",
           (user_id, first_name))
    cursor.execute("INSERT INTO orders (chat_id, user_id, order_text) VALUES (?, ?, ?)", 
                   (chat_id, user_id, order_text))
    conn.commit()
    conn.close()
    bot.send_message(chat_id, f"Order added: {order_text}")


@bot.message_handler(commands=['editorder'])
def edit_order(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    new_order_text = message.text[len('/editorder '):].strip()
    if not is_active_session(chat_id):
        bot.send_message(chat_id, "No active order session. Start a new session with /startorder.")
        return

    user_id = message.from_user.id
    new_order_text = message.text[len('/editorder '):]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM orders 
        WHERE chat_id = ? AND user_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (chat_id, user_id))
    order = cursor.fetchone()
    if order:
        # Update the most recent order
        cursor.execute("UPDATE orders SET order_text = ? WHERE id = ?", (new_order_text, order[0]))
        conn.commit()
        bot.send_message(chat_id, "Your most recent order has been updated.")
    else:
        bot.send_message(chat_id, "You do not have any orders to edit.")

    conn.close()


@bot.message_handler(commands=['cancelorder'])
def cancel_order(message):
    chat_id = message.chat.id
    if not is_active_session(chat_id):
        bot.send_message(chat_id, "No active order session. Start a new session with /startorder.")
        return

    if chat_id in timers:
        timers[chat_id].cancel()
        del timers[chat_id]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM orders WHERE chat_id = ?", (chat_id,))
    cursor.execute("UPDATE order_sessions SET active = 0 WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()

    bot.send_message(chat_id, "All orders have been deleted.")


@bot.message_handler(commands=['vieworder'])
def view_order(message):
    chat_id = message.chat.id

    if not is_active_session(chat_id):
        bot.send_message(chat_id, "No active order session. Start a new session with /startorder.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    print("Fetching orders for chat_id:", chat_id)  # Debug print
    cursor.execute("""
        SELECT u.first_name, o.order_text 
        FROM orders o 
        JOIN users u ON o.user_id = u.user_id 
        WHERE o.chat_id = ? AND o.status = 'pending'
    """, (chat_id,))
    orders = cursor.fetchall()
    print("Orders fetched:", orders)  # Debug print
    conn.close()

    if not orders:
        bot.send_message(chat_id, "There are no orders to view.")
        return

    order_summary = "\n".join(f"{order[0] or 'Unknown user'}: {order[1]}" for order in orders)
    bot.send_message(chat_id, f"Current orders:\n{order_summary}")


@bot.message_handler(commands=['removeorder'])
def remove_order(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not is_active_session(chat_id):
        bot.send_message(chat_id, "No active order session. Start a new session with /startorder.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if the user has an order
    cursor.execute("SELECT id FROM orders WHERE chat_id = ? AND user_id = ? ORDER BY id DESC LIMIT 1", (chat_id, user_id))
    order = cursor.fetchone()

    if order:
        # Delete the user's order
        cursor.execute("DELETE FROM orders WHERE id = ?", (order[0],))
        bot.send_message(chat_id, "Your order has been removed.")
    else:
        bot.send_message(chat_id, "You do not have an order to remove.")

    conn.commit()
    conn.close()



@bot.message_handler(commands=['finalise'])
def finalise_order(message):
    chat_id = message.chat.id

    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch the active session and purchaser ID
    cursor.execute("SELECT purchaser_id FROM order_sessions WHERE chat_id = ? AND active = 1", (chat_id,))
    session = cursor.fetchone()

    if not session:
        bot.send_message(chat_id, "No active order session. Start a new session with /startorder.")
        conn.close()
        return

    purchaser_id = session[0]

    # Fetch orders only from the current active session
    # Assuming orders from the current session are not marked as 'completed'
    cursor.execute("""
        SELECT o.id, u.first_name, o.order_text 
        FROM orders o 
        JOIN users u ON o.user_id = u.user_id 
        WHERE o.chat_id = ? AND o.status != 'completed'
    """, (chat_id,))
    orders = cursor.fetchall()

    # Cancel any existing timer
    if chat_id in timers:
        timers[chat_id].cancel()
        del timers[chat_id]

    # Process the fetched orders
    if not orders:
        bot.send_message(chat_id, "No active orders to finalise.")
    else:
        # Create order summary for the group
        order_summary_group = "\n".join(f"{order[1]}: {order[2]}" for order in orders)
        bot.send_message(chat_id, f"Order finalised. Summary:\n{order_summary_group}")

        # Order summary for the purchaser with detailed information (using order ID)
        order_summary_purchaser = "\n".join(f"{order[0]}: {order[1]} - {order[2]}" for order in orders)
        if purchaser_id:
            try:
                bot.send_message(purchaser_id, f"Here is the final order list for you to purchase:\n{order_summary_purchaser}")
            except Exception as e:
                bot.send_message(chat_id, "Failed to send order list to the purchaser. They might need to start a chat with the bot first.")

    # Mark orders as completed and update the session to 'finalised'
    cursor.execute("UPDATE orders SET status = 'completed' WHERE chat_id = ?", (chat_id,))
    cursor.execute("UPDATE order_sessions SET status = 'finalised', active = 0 WHERE chat_id = ?", (chat_id,))
    conn.commit()
    print("Session finalised for chat_id:", chat_id) 
    conn.close()





@bot.message_handler(commands=['submitprice'])
def submit_price(message):
    print("Submit price command received")
    chat_id = message.chat.id
    user_id = message.from_user.id  # User ID of the person sending the command

    # Validate command format and price
    parts = message.text.split()
    if len(parts) < 3:
        bot.send_message(message.chat.id, "Please use the format: /submitprice [order ID] [price]")
        return
    try:
        order_id, price = int(parts[1]), float(parts[2])
    except ValueError:
        bot.send_message(message.chat.id, "Please enter a valid price.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch the session and purchaser_id based on the user_id
    cursor.execute("SELECT chat_id, purchaser_id FROM order_sessions WHERE purchaser_id = ? AND status = 'finalised'", (user_id,))
    session = cursor.fetchone()

    if session:
        group_chat_id, purchaser_id = session  # chat_id of the group where the session was finalized

        # Update order price using group_chat_id
        cursor.execute("UPDATE orders SET price = ? WHERE id = ? AND chat_id = ?", (price, order_id, group_chat_id))
        if cursor.rowcount == 0:
            bot.send_message(message.chat.id, "Order not found or you're not authorized to update this order.")
            conn.close()
            return

        # Price updated successfully
        bot.send_message(message.chat.id, f"Price for order ID {order_id} updated to {price}.")


        # Calculate total amounts owed by each user
        cursor.execute("""
            SELECT o.user_id, o.id, SUM(o.price)
            FROM orders o
            WHERE o.chat_id = ? AND o.price IS NOT NULL
            GROUP BY o.user_id, o.id
        """, (group_chat_id,))
        amounts_owed = cursor.fetchall()

        for user_id, order_id, amount in amounts_owed:
            if user_id == purchaser_id:
                # If the purchaser is the same as the one who ordered
                bot.send_message(user_id, f"This is your item (Order ID {order_id}). Consider it paid!")
            else:
                # Fetch and send PayLah payment links to other users
                cursor.execute("SELECT paylah_link FROM user_paylah_links WHERE user_id = ?", (purchaser_id,))
                paylah_link_row = cursor.fetchone()
                paylah_link = paylah_link_row[0] if paylah_link_row else None

                if paylah_link:
                    try:
                        bot.send_message(user_id, f"Your total amount to pay is {amount}. Please make the payment using this PayLah link: {paylah_link}")
                    except Exception as e:
                        print(f"Error sending message to user_id {user_id}: {e}")

        conn.close()
    else:
        bot.send_message(message.chat.id, "Price submission is only allowed after the session has been finalised or you are not the purchaser.")





if __name__ == '__main__':
    bot.polling(none_stop=True)
