
import requests
import sqlite3
import time
import re
from bs4 import BeautifulSoup

# Googleのリポジトリ一覧ページ
url = "https://github.com/orgs/google/repositories"

headers = {
    "User-Agent": "Mozilla/5.0"
}

# データベースに接続
con = sqlite3.connect("repositories.db")
cur = con.cursor()

# テーブルを作成
cur.execute("""
CREATE TABLE IF NOT EXISTS repositories (
    name TEXT PRIMARY KEY,
    language TEXT,
    stars INTEGER
)
""")

# 進捗を記録するテーブル
cur.execute("""
CREATE TABLE IF NOT EXISTS progress (
    id INTEGER PRIMARY KEY,
    last_page INTEGER
)
""")

cur.execute("""
INSERT OR IGNORE INTO progress (id, last_page)
VALUES (1, 0)
""")
con.commit()


# スター数を数値に変換する関数
def convert_stars(text):
    text = text.strip().replace(",", "")
    match = re.search(r"([\d.]+)\s*([kKmM]?)", text)

    if not match:
        return 0

    number = float(match.group(1))
    unit = match.group(2).lower()

    if unit == "k":
        number *= 1000
    elif unit == "m":
        number *= 1000000

    return int(number)


# 最後に取得したページの次から再開
cur.execute("SELECT last_page FROM progress WHERE id = 1")
last_page = cur.fetchone()[0]
page = last_page + 1

completed = False

try:
    while True:
        print(f"\n{page}ページ目を取得中...")

        # アクセスの間隔を空ける
        time.sleep(1)

        response = requests.get(
            url,
            headers=headers,
            params={"page": page},
            timeout=30
        )

        # アクセス制限への対応
        if response.status_code == 429:
            print("アクセス制限（429）が発生しました。")
            print("時間を空けてから再実行してください。")
            break

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # リポジトリ一覧を取得
        repositories = soup.select("li.listItem__X41oTe")

        # リポジトリがない場合は取得終了
        if not repositories:
            print("\n次のページにリポジトリがありません。")
            print(f"{last_page}ページ目までの取得が完了しました。")
            completed = True
            break

        count = 0

        for repo in repositories:
            # リポジトリ名
            name = None

            for link in repo.select("a[href]"):
                href = link.get("href", "")

                if re.fullmatch(r"/google/[^/]+", href):
                    name = href.split("/")[-1]
                    break

            if not name:
                continue

            # 主要言語
            language_tag = repo.select_one(
                'span[class*="PrimaryLanguageName"]'
            )

            language = (
                language_tag.get_text(strip=True)
                if language_tag else "不明"
            )

            # スター数
            star_tag = repo.select_one(
                'a[href$="/stargazers"]'
            )

            stars = (
                convert_stars(star_tag.get_text(strip=True))
                if star_tag else 0
            )

            # データベースに保存
            cur.execute("""
            INSERT OR REPLACE INTO repositories
            (name, language, stars)
            VALUES (?, ?, ?)
            """, (name, language, stars))

            count += 1

        # データを保存
        con.commit()

        # 取得済みページを記録
        cur.execute("""
        UPDATE progress
        SET last_page = ?
        WHERE id = 1
        """, (page,))
        con.commit()

        print(f"{count}件を保存しました。")

        # 次のページがあるか確認
        next_page = soup.select_one('a[rel="next"]')

        if not next_page:
            print("\n最後のページに到達しました。")
            completed = True
            break

        page += 1

except requests.RequestException as e:
    print("通信エラーが発生しました。")
    print(e)

finally:
    # 保存件数を確認
    cur.execute("SELECT COUNT(*) FROM repositories")
    total = cur.fetchone()[0]

    cur.execute("SELECT last_page FROM progress WHERE id = 1")
    saved_page = cur.fetchone()[0]

    print("\n===== データベースの内容 =====")

    # SELECTでデータを表示
    cur.execute("""
    SELECT name, language, stars
    FROM repositories
    ORDER BY stars DESC
    """)

    for row in cur.fetchall():
        print(row)

    print(f"\n保存したリポジトリ総数: {total}件")
    print(f"最後に取得したページ: {saved_page}ページ目")

    con.close()

    if completed:
        print("\n全ページの取得が終了しました。")
    else:
        print("\n取得は途中で終了しました。")
        print("次回は最後に取得したページの次から再開します。")
