# Deploying KnowledgeVault to AWS (KV-41)

One small AWS server runs three containers: Postgres with pgvector, the
backend, and Caddy, which serves the API over HTTPS. The result is an address
like `https://3-91-12-45.sslip.io` that works from any machine. Expect about
$20 a month while it runs; new AWS accounts usually come with credits, so check
**Billing and Cost Management, then Credits**.

| File | What it is |
|---|---|
| `docker-compose.prod.yml` (repo root) | The three containers. Only Caddy is open to the internet. |
| `deploy/Caddyfile` | Tells Caddy to get the HTTPS certificate and pass requests to the backend. |
| `.env.example` (repo root) | The three settings the server needs: `API_HOST`, `POSTGRES_PASSWORD`, `CORS_ORIGINS`. |
| `deploy/smoke_test.py` | Checks a running API end to end: health, upload, search, then deletes its own test document. |

The console screens change now and then, so a button may be named a little
differently. Use the same AWS region for everything (**N. Virginia, us-east-1**
is closest to Worcester).

## 1. AWS account (skip if you have one)

1. Create an account at <https://aws.amazon.com> (a card is required).
2. Turn on MFA for the root user: account menu, **Security credentials**,
   **Assign MFA device**.
3. Set a billing alert so nothing surprises you: **Billing and Cost
   Management, Budgets, Create budget**, a monthly cost budget of $25 with an
   email alert.

## 2. Launch the server

**EC2, Launch instance**:

- **Name:** `knowledgevault`
- **Image:** Ubuntu Server 24.04 LTS
- **Instance type:** `t3.small` (2 GB of memory; the embedding model needs more than a `t3.micro` has)
- **Key pair:** create a new one (RSA, `.pem`). Keep the file somewhere safe,
  for example `C:\Users\<you>\.ssh\knowledgevault.pem`. You cannot download it again.
- **Network settings, Edit**, new security group with three rules:
  SSH (22) from **My IP**, HTTP (80) from **Anywhere**, HTTPS (443) from **Anywhere**
- **Storage:** 20 GiB gp3

Then give it a fixed address: **EC2, Elastic IPs, Allocate Elastic IP address,
Associate** it with the instance. Without this the IP changes whenever the
server is stopped and started, and the HTTPS name below would break. Write the
IP down.

## 3. Connect and install Docker

From PowerShell on your computer (use your key path and the Elastic IP):

```powershell
ssh -i C:\Users\<you>\.ssh\knowledgevault.pem ubuntu@<ELASTIC-IP>
```

If Windows says `UNPROTECTED PRIVATE KEY FILE`, fix the file's permissions once:

```powershell
icacls C:\Users\<you>\.ssh\knowledgevault.pem /inheritance:r
icacls C:\Users\<you>\.ssh\knowledgevault.pem /grant:r "$($env:USERNAME):(R)"
```

On the server:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
exit
```

Connect again with the same `ssh` command (so the group change applies), then
check that `docker compose version` prints a version.

## 4. Get the code and set the settings

```bash
git clone https://github.com/falcon883/knowledgevault.git
cd knowledgevault
cp .env.example .env
openssl rand -hex 16        # prints a password: copy it
nano .env
```

If the repository is private, `git clone` asks for your GitHub username and a
[personal access token](https://github.com/settings/tokens) as the password.

In `.env`, fill in:

| Setting | Value |
|---|---|
| `API_HOST` | The Elastic IP with dashes, then `.sslip.io`. IP `3.91.12.45` becomes `3-91-12-45.sslip.io`. (sslip.io is a free service that turns that name into the IP, so you do not need a domain.) |
| `POSTGRES_PASSWORD` | The password you just generated |
| `CORS_ORIGINS` | `http://localhost:5173` for now. When the frontend is deployed, add its address after a comma, for example `http://localhost:5173,https://app.example.com` |

Save with `Ctrl+O`, `Enter`, then `Ctrl+X`. `.env` stays on the server and is
never committed.

## 5. Start it

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

The first run takes 5 to 10 minutes (it builds the image and downloads the
embedding model). Check on it:

```bash
docker compose -f docker-compose.prod.yml ps        # db and backend should say "healthy"
docker compose -f docker-compose.prod.yml logs -f   # Ctrl+C stops watching, not the app
```

The tables are created on first start, so there is nothing else to set up.

## 6. Check it from your computer

1. Open `https://<API_HOST>/health` in a browser. You want a padlock,
   `"status": "ok"`, `"database": "ok"` and `"model_loaded": true`. The very
   first visit can take half a minute while Caddy gets the certificate; if the
   browser shows a certificate error, wait a minute and refresh.
2. Run the end-to-end check with the backend's virtual environment active:

   ```bash
   python deploy/smoke_test.py https://<API_HOST>
   ```

   Every line should say `[ok]`. It deletes the test document it uploads, so
   it is safe to run against real data.
3. Use the deployed API from your local frontend: in `frontend/`, create a file
   named `.env.local` containing `VITE_API_URL=https://<API_HOST>`, run
   `npm run dev`, and open `http://localhost:5173`.

## Everyday use

All of these run on the server, in the `knowledgevault` folder.

| Task | Command |
|---|---|
| Deploy a new version | `git pull` then `docker compose -f docker-compose.prod.yml up -d --build` |
| Change a setting | edit `.env` then `docker compose -f docker-compose.prod.yml up -d` |
| Read the backend log | `docker compose -f docker-compose.prod.yml logs -f backend` |
| Back up the database | `docker compose -f docker-compose.prod.yml exec -T db pg_dump -U knowledgevault knowledgevault > backup.sql` |

The containers start again on their own after a crash or a server reboot.

**Costs:** Stop the instance in the EC2 console when you do not need it (you
still pay a few dollars a month for the disk and the Elastic IP). When the
project is over, terminate the instance and release the Elastic IP.

## If something goes wrong

- **`Killed` while building:** the server ran out of memory. Add swap, then run
  the build again:
  `sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile`
- **The browser cannot connect:** check that the security group allows ports 80
  and 443 from anywhere, and that `docker compose ... ps` shows `caddy` running.
- **Certificate error that does not go away:** read
  `docker compose -f docker-compose.prod.yml logs caddy`. Usual causes are a
  typo in `API_HOST` or port 80 being blocked (the certificate check needs it).
- **`/health` says 503:** the database is not answering. Read `logs db`.
- **The frontend is blocked by CORS:** the browser console names the origin it
  used. Add exactly that to `CORS_ORIGINS` and run
  `docker compose -f docker-compose.prod.yml up -d`.
- **SSH stopped working:** your IP changed (a different Wi-Fi, say). Edit the
  SSH rule in the security group to your current IP.
