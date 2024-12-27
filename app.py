from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_sqlalchemy import SQLAlchemy
import os
import stripe
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

stripe.api_key = "sk_test_51I4ftiA2JgXeXni6hAGlAYFf35OAd1H49RExHdjfwum7Nyvy9jMmkMiOL8bTkHa0aodMxtRpLczq4bXgbxR7OF8A008iUGFYlt"

# 初始化 Flask 應用
app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ecommerce.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # 防止SQLAlchemy警告
db = SQLAlchemy(app)

# Flask-Login configuration
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # 登錄頁面的路由

# 商品模型
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return f'<Product {self.name}>'

# 購物車項目模型
class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    product = db.relationship('Product', backref=db.backref('cart_items', lazy=True))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # 添加 user_id 外鍵

    def __repr__(self):
        return f'<CartItem {self.product.name} x {self.quantity}>'

# 用戶模型
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 主頁路由
@app.route('/')
def index():
    products = Product.query.all()  # 查詢所有商品
    return render_template('index.html', products=products)

# 結帳路由
@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    # 計算總價（根據購物車中的商品）
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total_price = sum(item.quantity * item.product.price for item in cart_items)
    print(f"Cart Items: {cart_items}")
    print(f"Total Price: {total_price}")
    if request.method == 'POST':
        print("Form submitted successfully!")
        try:
            # 呼叫金流 API（以 Stripe 為例）
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[
                    {
                        'price_data': {
                            'currency': 'usd',
                            'product_data': {'name': item.product.name},
                            'unit_amount': int(item.product.price * 100),  # 金額以分計算
                        },
                        'quantity': item.quantity,
                    } for item in cart_items
                ],
                mode='payment',
                success_url=url_for('payment_success', _external=True),
                cancel_url=url_for('checkout', _external=True),
            )
            return redirect(session.url)
        except Exception as e:
            flash(f"Payment error: {e}", 'danger')
            return redirect(url_for('checkout'))
    
    # 顯示結帳頁面並傳遞總價
    return render_template('checkout.html', cart_items=cart_items, total_price=total_price)

@app.route('/payment_success', methods=['GET'])
@login_required
def payment_success():
    return render_template('success.html')  # 用來顯示成功信息

@app.route('/payment_failed', methods=['GET'])
@login_required
def payment_failed():
    return render_template('failed.html')  # 用來顯示支付失敗信息


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and user.password == password:  # 用實際的驗證方式替換這裡
            login_user(user)
            return redirect(url_for('index'))

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# 註冊頁面
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        print(f"Received username: {username}, email: {email}")  # 調試輸出

        # 檢查兩次密碼是否相同
        if password != confirm_password:
            flash('Passwords must match!', 'danger')
            return redirect(url_for('register'))

        # 檢查用戶名或電子郵件是否已經存在
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists!', 'danger')  # 顯示錯誤信息
            return redirect(url_for('register'))
        
        # 創建新用戶
        new_user = User(username=username, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

# 購物車頁面
@app.route('/cart', methods=['GET', 'POST'])
@login_required
def cart():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total_price = 0  # 初始化總價

    if request.method == 'POST':
        cart_item_id = request.form.get('cart_item_id')
        quantity = int(request.form.get('quantity'))

        # 查找購物車項目並更新數量
        cart_item = CartItem.query.get(cart_item_id)
        if cart_item:
            cart_item.quantity = quantity
            db.session.commit()  # 提交變更

    # 計算總價
    for item in cart_items:
        total_price += item.quantity * item.product.price

    return render_template('cart.html', cart_items=cart_items, total_price=total_price)

# 添加商品到購物車
@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
@login_required  # 確保用戶已經登錄
def add_to_cart(product_id):
    # 查找商品
    product = Product.query.get(product_id)
    if not product:
        return redirect(url_for('index'))

    # 查找購物車中是否已有該商品
    cart_item = CartItem.query.filter_by(product_id=product_id, user_id=current_user.id).first()
    if cart_item:
        # 如果商品已在購物車中，增加數量
        cart_item.quantity += 1
    else:
        # 創建新的購物車項目，並且設置 user_id
        cart_item = CartItem(product_id=product_id, user_id=current_user.id)
        db.session.add(cart_item)

    db.session.commit()
    return redirect(url_for('cart'))  # 重新導向到購物車頁面

# 更新購物車項目的數量
@app.route('/update_cart/<int:cart_item_id>', methods=['POST'])
@login_required  # 確保用戶已經登錄
def update_cart(cart_item_id):
    cart_item = CartItem.query.get(cart_item_id)
    if cart_item:
        quantity = request.form['quantity']
        if quantity.isdigit() and int(quantity) > 0:
            cart_item.quantity = int(quantity)
            db.session.commit()
    return redirect(url_for('cart'))

# 刪除購物車項目
@app.route('/remove_from_cart/<int:cart_item_id>', methods=['GET', 'POST'])
@login_required
def remove_from_cart(cart_item_id):
    cart_item = CartItem.query.filter_by(id=cart_item_id, user_id=current_user.id).first()
    if cart_item:
        db.session.delete(cart_item)
        db.session.commit()
    return redirect(url_for('cart'))  # 刪除後返回購物車頁面



# 主程式入口
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # 創建數據庫表格

        # 添加測試商品數據
        if Product.query.count() == 0:  # 如果沒有商品，則添加一個測試商品
            product = Product(
                name="Product 1",
                description="This is an amazing product.",
                price=49.99,
                image_url="product1.jpg"
            )
            db.session.add(product)
            db.session.commit()

    app.run(debug=True)
