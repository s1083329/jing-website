# jing-website

This is the website for [https://www.jingbirdnest.com](https://www.jingbirdnest.com).

本機使用 Conda，DigitalOcean 使用 Docker：見 [開發與部署說明](docs/docker.md)。

```sh
conda activate jing
# 首次啟動前，依部署說明設定 .env。
python -m flask --app app run --debug --port=5001
```
