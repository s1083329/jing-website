# Conda 開發與 Docker 部署

此專案是 Flask + SQLite；商品上傳使用 Cloudflare R2，AI 文案使用 Gemini。
本機使用 Conda 獨立環境，不需要安裝 Docker。DigitalOcean 需要 Docker Engine 和 Docker Compose **2.30.0 以上**（使用 raw env_file），伺服器備份需要 Python 3。
伺服器安裝請參考 [Ubuntu Docker Engine](https://docs.docker.com/engine/install/ubuntu/)。

## 本機開發：Conda

在專案根目錄執行：

```sh
conda activate jing
```

沿用既有 `jing` 環境（已確認 Python 3.10.20），不需要重新建立或更新環境。Docker 使用 Python 3.12，會自行安裝 `requirements.txt`；本機 Flask 開發不需要 Gunicorn。
`environment.yml` 僅供未來在其他電腦重建環境時參考，不要對現有環境執行建立指令。
Conda 與 Docker 仍有作業系統差異，上線前應在 Docker 驗證。

首次設定（已有 `.env` 時跳過複製）：

```sh
cp .env.example .env
chmod 600 .env
mkdir -p instance static/img
python -c 'import secrets; print(secrets.token_hex(32))'
```

將產生的隨機值填入 `.env` 的 `SECRET_KEY`，本機設定 `SESSION_COOKIE_SECURE=false`。
需要 R2 圖片上傳與 Gemini 文案功能時，填入開發用 keys；使用獨立測試 bucket。
Conda 只隔離 Python 套件，不會隔離專案資料庫或外部 API：本機仍讀取 `instance/database.db`。
請勿將正式資料放進 Git，也不要使用正式 R2 bucket 做刪除測試。

如果是全新資料庫，才執行：

```sh
python -m flask --app app init-db
python -m flask --app app create-admin admin
```

啟動網站：

```sh
python -m flask --app app run --debug --port=5001
```

開啟 http://127.0.0.1:5001，後台為 `/admin`。既有 SQLite 資料庫可直接使用，不必重建管理員。
每次開啟終端機，先 `conda activate jing`；完成後用 `conda deactivate` 離開環境。
未來修改依賴時，在已啟用的 `jing` 環境確認版本相容性後再安裝；伺服器則重新 build Docker 映像檔。
本機 Conda 環境不需複製到伺服器。

## 資料與機密

| 項目 | 保存位置 | 更新映像檔時 |
| --- | --- | --- |
| 程式、模板、CSS、JS | Docker 映像檔 | 更新 |
| API keys、SECRET_KEY | 主機 `.env`，啟動時注入 | 保留 |
| 商品、管理員 | 主機 `instance/database.db` | 保留 |
| 首頁／證書圖片 | 主機 `static/img/` | 保留，唯讀掛載 |
| 新商品圖片 | R2 bucket | 不受容器更新影響 |

Docker 不會取代 SSH 或 Git；SSH 用於管理伺服器，Git 用於取得程式，Docker 統一執行環境與版本。
這份設定採用伺服器從 Git 建立映像檔，不需要 registry 或 GitHub secrets。
`.dockerignore` 使用允許清單，資料庫、`.env`、SSH keys 不會送入 build context。
勿把正式資料庫覆蓋成本機資料庫，也不用每次更新重傳資料或 keys。
`.env` 以原始值注入，填 `KEY=value` 即可，不要在值外面加引號；若從舊 `.env` 搬移請移除包覆引號。
有 Docker 管理權限的人仍可讀取容器環境變數，請限制主機權限。

## 選用：本機 Docker 開發

使用上述 Conda 流程時可跳過本節。只有想在本機驗證容器時，才需要另外安裝 Docker Desktop。

```sh
cp .env.example .env
chmod 600 .env
mkdir -p instance static/img
```

填入隨機 `SECRET_KEY`（範例檔有產生指令）。需要圖片上傳或 AI 功能時填入各自的開發用 keys；未填時仍可瀏覽及管理既有資料，但外部功能不可用。
使用測試資料庫與獨立 R2 bucket，避免開發刪除正式圖片。
既有 `.env` 不要覆蓋；本機已有資料庫也不需要重建。

```sh
docker compose -f compose.yaml -f compose.dev.yaml build
docker compose -f compose.yaml -f compose.dev.yaml run --rm web flask --app app init-db
# 全新資料庫才需要建立管理員，密碼會互動詢問：
docker compose -f compose.yaml -f compose.dev.yaml run --rm web flask --app app create-admin admin
docker compose -f compose.yaml -f compose.dev.yaml up
```

開啟 http://localhost:8000；後台在 `/admin`。修改 Python／模板／CSS／JS 即時生效，修改依賴需重新 build。
容器以 UID/GID `1000:1000` 執行，與目前 VPS 的資料庫擁有者一致。其他 Linux 電腦需確認 `instance` 及資料庫可由 UID 1000 讀寫。
macOS Docker Desktop 使用檔案共享處理掛載權限。
停止開發：`docker compose -f compose.yaml -f compose.dev.yaml down`。

## DigitalOcean 首次搬移（現有 Droplet + 主機 Nginx）

此流程假設現有主機 Nginx 負責 HTTPS。若使用 App Platform、容器 Nginx 或其他架構，應先調整對應入口設定。
先確認原服務的 systemd unit、程式目錄、資料庫位置和 Nginx upstream；此 repository 未包含這些正式機資訊。

1. 安裝 Docker Engine 與 Compose plugin，檢查 `docker compose version`。
2. 把包含這些 Docker 設定的 Git commit 部署至伺服器。可沿用原專案目錄；保留原 `.env`、`instance`、`static/img`。
3. 若改用新目錄，先建立目錄、複製 `.env` 和`static/img` 圖片資料夾。SQLite 必須在停止舊服務寫入後複製，或使用下方備份工具產生一致快照；不要只複製正在寫入的 `.db` 而漏掉 WAL。
4. 在正式 `.env` 設定 `SESSION_COOKIE_SECURE=true`（對外必須為 HTTPS），保留原 `SECRET_KEY` 以維持 session；`APP_PORT=8000`，若被占用可改成其他閒置 port。容器固定讀 `/app/instance/database.db`。
5. 確認資料庫與所有網站圖片存在。`static/img` 未納入 Git，只有 git clone 不會取得這些圖片。

在專案根目錄執行：

```sh
chmod 600 .env
mkdir -p backups
# 先備份；請以有資料庫讀取權限的使用者執行。
python3 scripts/backup.py
docker compose build --pull
```

安排短暫維護時間，停止**實際的**舊應用服務（例如 `sudo systemctl stop <原服務名稱>`，不要直接照抄佔位文字）。
停止後再執行一次備份；如搬至新目錄，將此最後快照複製為新目錄的 `instance/database.db`。
如果沿用原資料目錄，不必複製。確認現有擁有者與權限：

```sh
id ubuntu
ls -ldn instance
ls -ln instance/database.db
```

Dockerfile 與 Compose 都設定為 UID/GID `1000:1000`。目前 VPS 的 `instance` 和 `database.db` 已屬於 `1000:1000`，且擁有者可讀寫，因此不需要 chown 或新增群組權限；`ubuntu` 也能繼續執行備份。
若使用其他主機或還原備份，需重新確認目錄與資料庫的擁有者可讀寫，目錄也必須可進入。
圖片目錄需要容器使用者可讀且可進入，但不需要寫入。

既有正式資料庫**不用**執行 init-db 或 create-admin。首次啟動：

```sh
IMAGE_TAG=$(git rev-parse HEAD) docker compose build
IMAGE_TAG=$(git rev-parse HEAD) docker compose up -d --no-build --wait --wait-timeout 120
curl --fail http://127.0.0.1:8000/healthz
docker compose logs --tail=100 web
```

`/healthz` 會確認商品與管理員資料表可查詢；缺少資料庫 schema 時回傳 503。
全新網站才執行前述 init-db 和 create-admin。

將既有 Nginx HTTPS server block 的應用入口指向容器，保留現有憑證及網域設定：

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 130s;
}
```

若修改 APP_PORT，upstream 要同步修改。保留符合目前圖片上傳需求的 `client_max_body_size`。
若既有 Nginx 直接提供 `/static/`，其 alias 必須指向正確圖片目錄。
執行 `sudo nginx -t` 成功後再 `sudo systemctl reload nginx`。
確認首頁圖片、證書、商品列表、登入、商品增修以及 R2／Gemini 功能。
確認穩定後停用舊應用服務自動啟動，保留 Nginx 與 HTTPS 憑證更新服務。
Docker 僅將服務綁定至主機 loopback，不需對外開放 8000。

## 後續更新

本機開發與驗證後 commit / push。伺服器執行：

```sh
git pull --ff-only
bash scripts/deploy.sh
```

腳本要求工作目錄乾淨，以完整 Git SHA 標記映像檔，先 build，再以 SQLite backup API 備份資料，最後重建容器並等待健康檢查。
若健康檢查失敗且舊容器的映像名稱符合本專案，會嘗試恢復上一個映像；請檢查終端輸出與 logs。
此方式更新時有短暫中斷，並非零停機。單次部署請勿並行執行。
程式更新不會自動做 schema migration；未來修改資料表應另寫可回復的遷移流程。
請保留部署輸出的前一個映像 tag，不要隨意 prune 掉它。

手動回復上一個程式版本：

```sh
IMAGE_TAG=<前一版完整Git-SHA> docker compose up -d --no-build --wait --wait-timeout 120
```

若該版本改過 Compose 設定，也需取回對應版本設定。程式回復不會回復資料庫，避免丟失更新後新增的資料。
只有確認需要資料回復時，停止容器、先備份當前資料庫，再還原指定快照，處理舊 WAL/SHM 並恢復 UID/GID 權限。
首次切換若失敗，可停掉容器，恢復原服務讀寫權限與 Nginx upstream 後再啟動舊服務。

## 日常管理

```sh
docker compose ps
docker compose logs --tail=100 -f web
python3 scripts/backup.py
docker compose stop
docker compose start
```

備份寫入 `backups/`，不納入 Git。請定期備份並另外存到其他主機或儲存服務，主機內備份不能防止 Droplet 遺失。
`.env` 和本機圖片也應有獨立私密備份；R2 物件需另行規劃保留策略。
修改 `.env` 後執行 `docker compose up -d --no-build --force-recreate` 時需加上目前的 `IMAGE_TAG`，以免套用預設 local 映像。
不要把 `docker compose config` 的完整輸出貼到公開地方，它可能包含 keys。

設計依據：[Docker Compose production](https://docs.docker.com/compose/how-tos/production/)、[Flask Gunicorn](https://flask.palletsprojects.com/en/stable/deploying/gunicorn/)。
