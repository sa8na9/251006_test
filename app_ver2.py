from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import random
from datetime import datetime, timezone, timedelta

app = Flask(__name__)

app.config['SECRET_KEY'] = 'abc'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'

# flaskとSQLAlchemyの関連付け
db = SQLAlchemy(app)

# flaskとflask-loginの関連付け
login_manager = LoginManager(app)

login_manager.login_view = 'login'

# DB設定
## ユーザー情報
class User(UserMixin, db.Model):
    __tablename__ = 'user'
    __table_args__ = {'sqlite_autoincrement':True}

    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(50), unique=True)
    user_password = db.Column(db.String(256))

## 対戦履歴
class BattleLog(db.Model):
    __tablename__ = 'game_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    player_hand_name = db.Column(db.String(20), nullable=False)
    com_hand_name = db.Column(db.String(20), nullable=False)
    user_result = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now(timezone.utc))

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

# 手リスト
hand = ["rock(0)", "scissors(1)", "paper(2)", "water(3)", "air(4)", "sponge(5)", "fire(6)"]

# 手の種類数
hand_num = len(hand)

# 力関係　{自分の手: 自分が勝てる相手の手のインデックス}
power_balance = {
    0: [1, 5, 6],
    1: [2, 4, 5],
    2: [0, 3, 4],
    3: [0, 1, 6],
    4: [0, 3, 6],
    5: [2, 3, 4],
    6: [1, 2, 5]
    }

# ---

# インデックス
@app.route("/")
def index():
    return render_template('index.html', user_name=current_user)

# ユーザー登録
@app.route("/signup", methods=["get", "post"])
def signup():
    if request.method == 'GET':
        return render_template('signup.html')
    
    name = request.form.get('name')
    password = request.form.get('password')

    # name重複チェック
    existing_user = User.query.filter_by(user_name=name).first()

    if existing_user:
        flash("その名前はすでに登録されています。")
        return redirect(url_for('signup'))
    
    # パスワードのハッシュ化
    hashed_password = generate_password_hash(password)

    # DB登録
    user = User(
        user_name=name,
        user_password=hashed_password,
    )
    db.session.add(user)
    db.session.commit()

    flash("正常に登録されました。", 'success')
    return redirect(url_for('index'))

# ログイン
@app.route('/login', methods=["get", "post"])
def login():
    if request.method == 'POST':
        name = request.form.get('name')
        password = request.form.get('password')

        # 登録ユーザーを取得
        user = User.query.filter_by(user_name=name).first()

        # 認証処理
        if user and check_password_hash(user.user_password, password):  

            # 認証処理を記録  （ログイン状態にする）
            login_user(user)
            return redirect(url_for('battle'))
        
        # elseの場合
        flash("名前またはパスワードが不正です。")
        # ↓に流れる

    return render_template('login.html')

# ログアウト
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# 勝負画面
@app.route("/battle")
@login_required
def battle():
    return render_template('battle.html', hands=hand)

# APIを用いて結果をjsonで返す
@app.route("/api/play", methods=["POST"])
def api_play():
    # 手の取得、検証
    # 手違いでindexのみ手が増えたときなどのため
    try:
        player_hand_index = int(request.form.get('player_hand'))

    except(TypeError, ValueError):
        # jsonで返す
        return jsonify(error="エラー")
    
    if not (0 <= player_hand_index < hand_num):
        return jsonify(error="エラー")

    # コンピュータの手（インデックス）をランダムに取得
    com_hand_index = random.randint(0, hand_num - 1)

    # 勝者出力メッセージ
    result_text = ""

    # あいこ
    if player_hand_index == com_hand_index:
        result_text = "あいこ"
        user_result = "draw"

    # 勝ち
    elif com_hand_index in power_balance[player_hand_index]:
        result_text = "かち"
        user_result = "win"

    # 負け
    else:
        result_text = "まけ"
        user_result = "lose"

    JST = timezone(timedelta(hours=9))

    log = BattleLog(
    user_id=current_user.id,
    player_hand_name=hand[player_hand_index],
    com_hand_name=hand[com_hand_index],
    user_result=user_result, 
    timestamp=datetime.now(JST)
    )
    db.session.add(log)
    db.session.commit()

    # JSONレスポンス
    response_data = {
        "player_hand_index": player_hand_index,
        "player_hand_name": hand[player_hand_index],
        "com_hand_index": com_hand_index,
        "com_hand_name": hand[com_hand_index],
        "result_text": result_text
    }

    # DB登録
    # user = User(user_result=user_result)
    # db.session.add(user)
    # db.session.commit()

    # JSONデータを返す
    return jsonify(response_data)

# 対戦履歴
@app.route('/battle_log')
@login_required
def battle_log():
    # 現在のユーザーIDから対戦履歴を取得、日付でソート
    game_logs = BattleLog.query.filter_by(user_id=current_user.id).order_by(BattleLog.timestamp.desc()).all()

    return render_template('battle_log.html', game_logs=game_logs, user_name=current_user.user_name)

# ---

if __name__ == '__main__':
    app.run('0.0.0.0', 80, True)