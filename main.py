
import requests
import sqlite3
import time
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# GitHubのGoogleリポジトリ一覧
url = "https://github.com/orgs/google/repositories"

headers = {
    "User-Agent": "Mozilla/5.0"
}

# データベースを作成・接続
con = sqlite3.connect("repositories.db")
cur = con.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS repositories (
    name TEXT PRIMARY KEY,
    language TEXT,
    stars INTEGER
)
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


# ページ番号
page = 1

while True:
    print(f"{page}ページ目を取得中...")

    # アクセスの間隔を空ける
    time.sleep(5)

    response = requests.get(
        url,
        headers=headers,
        params={"page": page},
        timeout=30
    )

    # アクセス制限の場合は停止
    if response.status_code == 429:
        print("アクセス制限（429）が発生しました。")
        print("保存済みのデータは残っています。")
        break

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # リポジトリ一覧を取得
    repositories = soup.select("li.listItem__X41oTe")

    if not repositories:
        print("リポジトリを取得できませんでした。")
        print("HTMLの構造が変わった可能性があります。")
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

        language = language_tag.get_text(strip=True) if language_tag else "不明"

        # スター数
        star_tag = repo.select_one('a[href$="/stargazers"]')

        stars = convert_stars(star_tag.get_text(strip=True)) if star_tag else 0

        # データベースに保存
        cur.execute("""
        INSERT OR REPLACE INTO repositories
        (name, language, stars)
        VALUES (?, ?, ?)
        """, (name, language, stars))

        count += 1

    # ページごとに保存
    con.commit()

    print(f"{count}件を保存しました。")

    # 次のページがあるか確認
    next_page = soup.select_one('a[rel="next"]')

    if not next_page:
        print("最後のページに到達しました。")
        break

    page += 1

# 保存したデータを表示
print("\n===== データベースの内容 =====")

cur.execute("""
SELECT name, language, stars
FROM repositories
ORDER BY stars DESC
""")

for row in cur.fetchall():
    print(row)

con.close()

print("\n処理が終了しました。")
