from flask import Flask, request, render_template, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from PIL import Image
import io
import os
from datetime import datetime
from huggingface_hub import InferenceClient
import base64
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_secret_key_here-12345'  # Change this to a random secret key


# Database initialization
def init_db():
    conn = sqlite3.connect('image_gen.db')
    c = conn.cursor()

    # Create users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # Create images table
    c.execute('''CREATE TABLE IF NOT EXISTS images
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  prompt TEXT NOT NULL,
                  image_data BLOB NOT NULL,
                  generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')

    conn.commit()
    conn.close()


init_db()


# Image generation function
def generate_image(prompt):
    client = InferenceClient(

        model = "black-forest-labs/FLUX.1-dev",
        token = os.getenv("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")
    )
    try:
        # Generate image with proper error handling
        image = client.text_to_image(
            prompt=prompt,
            model="black-forest-labs/FLUX.1-dev"
        )
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
    except Exception as e:
        print(f"Full error: {e}")
        raise


# User registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            flash('Username and password are required')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)

        try:
            conn = sqlite3.connect('image_gen.db')
            c = conn.cursor()
            c.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                      (username, hashed_password))
            conn.commit()
            flash('Registration successful! Please log in.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists')
            return redirect(url_for('register'))
        finally:
            conn.close()

    return render_template('register.html')


# User login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('image_gen.db')
        c = conn.cursor()
        c.execute('SELECT id, password FROM users WHERE username = ?', (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            session['username'] = username
            flash('Logged in successfully!')
            return redirect(url_for('generate'))
        else:
            flash('Invalid username or password')
            return redirect(url_for('login'))

    return render_template('login.html')


# Image generation endpoint
@app.route('/generate', methods=['GET', 'POST'])
def generate():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        prompt = request.form['prompt']
        try:
            # Generate image
            image_data = generate_image(prompt)

            # Convert to base64 for HTML display
            import base64
            img_base64 = base64.b64encode(image_data).decode('utf-8')

            # Store in database (your existing code)
            conn = sqlite3.connect('image_gen.db')
            c = conn.cursor()
            c.execute('INSERT INTO images (user_id, prompt, image_data) VALUES (?, ?, ?)',
                      (session['user_id'], prompt, image_data))
            conn.commit()
            conn.close()

            # Display the image immediately
            return render_template('result.html',
                                   prompt=prompt,
                                   image_data=img_base64)  # Pass base64 string

        except Exception as e:
            flash(f'Error generating image: {str(e)}')
            return redirect(url_for('generate'))

    return render_template('generate.html')

# User gallery
@app.route('/gallery')
def gallery():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('image_gen.db')
    c = conn.cursor()
    c.execute('''SELECT id, prompt, image_data, generated_at 
                 FROM images 
                 WHERE user_id = ? 
                 ORDER BY generated_at DESC''',
              (session['user_id'],))

    images = []
    for img in c.fetchall():
        # Convert each image to base64
        img_base64 = base64.b64encode(img[2]).decode('utf-8')
        images.append({
            'id': img[0],
            'prompt': img[1],
            'image_data': img_base64,
            'generated_at': img[3]
        })

    conn.close()
    return render_template('gallery.html', images=images)

# Logout
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('Logged out successfully')
    return redirect(url_for('login'))

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('generate'))
    return redirect(url_for('login'))



if __name__ == '__main__':
    app.run(debug=True)
