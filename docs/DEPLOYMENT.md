# BA3073 deployment and submission guide

This guide accompanies the assignment README. Commands below are procedures;
they are not evidence that a deployment was performed.

## Local Windows deployment

Start Docker Desktop. In PowerShell, from the project root:

```powershell
docker compose -p ai-learning-assistant up --build -d --wait
curl.exe -fsS http://127.0.0.1:14242/health
```

The default port is bound to loopback. Open `http://127.0.0.1:14242/ui/`.
Use Git Bash to run the teacher's evidence command:

```bash
bash scripts/check-local-ui.sh --open
```

Capture the actual browser window with its address bar visible; an HTTP status
check alone does not demonstrate rendering. Keep `local-ui-check.txt` separately
from the source repository.

Put the shared Qwen key in the ignored `data/model-secrets.env` file, or save a
personal key in the app's model editor. Never paste a key into a tracked file.
The new QianWen platform and the older DashScope service use different endpoints.
For a new-platform key, configure the following non-secret override in `.env`:

```text
MODEL_BASE_URL=https://maas.qianwenaiapi.com/compatible-mode/v1
```

The supplied `qwen3.6-flash` model can remain selected when the platform lists it.
Verify through the model connection test and an actual generation run.

## ACR image delivery

Open <https://cr.console.aliyun.com>. Under the instance list, select the existing
personal instance. Check other regions if the current region is empty; an
account may already have its personal instance elsewhere. In the instance:

1. Open repository management, then namespaces. Use or create a namespace.
2. Open image repositories. Use or create a private local repository called
   `ai-learning-assistant`.
3. Copy its complete public image address from the repository's operation guide.
   Registry hostnames vary; use the console value instead of guessing one.
4. Under access credentials, find the registry username and set a registry
   password if necessary. This is separate from the ECS password. Log in with
   the console's Docker login command and type the password interactively.

In local PowerShell, replace the placeholder with the complete address:

```powershell
$env:AILA_IMAGE = 'YOUR_REGISTRY/YOUR_NAMESPACE/ai-learning-assistant:ba3073'
docker build --platform linux/amd64 -t $env:AILA_IMAGE .
docker push $env:AILA_IMAGE
docker image inspect $env:AILA_IMAGE --format '{{.Os}}/{{.Architecture}} {{json .RepoDigests}}'
```

This matches an x86_64 ECS. An ARM ECS requires an ARM image and a corresponding
Compose platform change. Record the real pushed digest; do not infer it from
an earlier local build. ACR personal edition is intended for learning/testing;
eligibility and free limits are subject to the console.

## ECS deployment and Task 2 evidence

Preserve any existing Nginx sites. Install Docker and Compose on Ubuntu if absent:

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
```

Copy the project source to a separate directory, such as
`/opt/ai-learning-assistant`. Do not upload local `data/`, `workspace/`, or
dependencies as source. Create private runtime directories on ECS and configure
the shared key there, or use an account-specific key through a secure connection.
Keep SQLite, the encryption master key, and generated artifacts persistent.

Create an ignored ECS `.env` with the actual pushed image reference:

```text
AILA_IMAGE=YOUR_REGISTRY/YOUR_NAMESPACE/ai-learning-assistant:ba3073
AILA_BIND_ADDRESS=0.0.0.0
MODEL_BASE_URL=https://maas.qianwenaiapi.com/compatible-mode/v1
```

Use a digest reference after obtaining the pushed digest if possible. On ECS,
log in to the same registry, then run:

```bash
sudo docker compose -p ai-learning-assistant -f compose.ecs.yml pull
sudo docker compose -p ai-learning-assistant -f compose.ecs.yml up -d --wait
sudo docker ps
curl -fsS http://127.0.0.1:14242/health
```

Before the external test, configure the ECS security group: allow TCP 14242 from
the student's current public IPv4 address with `/32` only. Avoid `0.0.0.0/0` for
14242. Also restrict SSH to the required administrative source. A laptop's LAN
address and the ECS public address are not the student's public source address.

Open `http://ECS_PUBLIC_IPV4:14242/ui/` on the student's computer and capture the
successful browser interface with its address bar. On ECS record the teacher's
check, using the ECS public IP:

```bash
sudo bash scripts/check-ecs-docker.sh ECS_PUBLIC_IPV4
```

The script uses `compose.ecs.yml` and the canonical `ai-learning-assistant`
project name. Set `AILA_COMPOSE_FILE` if using another deployment file.
Retrieve `ecs-docker-check.txt` from ECS. A check
from ECS and a browser check from the laptop are separate pieces of evidence.

## Domain purchase and the mainland hosting prerequisite

First establish whether a suitable domain/subdomain is already available.
For a new domain, open <https://wanwang.aliyun.com>, search the preferred name,
compare its first-year and renewal prices, select one year, and avoid optional
paid add-ons that are unnecessary for the assignment. Availability and prices
must be checked at purchase time.

The owner must create an individual domain information template, complete
required identity/email verification, review the exact order, and pay. Identity
documents and purchase credentials belong in the provider's own interface,
never in the assignment report or repository. Confirm the domain's final state
is normal; payment alone does not prove registration succeeded.

For a mainland China ECS, the website must complete ICP filing before public
domain access. Buying a domain and adding an A record does not complete filing.
The official personal-site guidance estimates approximately 3-22 working days.
If the deadline is too close, ask the instructor about an approved existing
domain/subdomain or hosting arrangement. Do not claim HTTPS completion while
filing or the domain remains pending. A different hosting region would require
reviewing its costs and applicable requirements before creating new resources.

Once the domain is ready, add an A record with a host such as `ai`, pointing to
the chosen ECS public IPv4. Use a domain you control. A generic IP-to-domain
mapping service is not evidence of controlling a domain.

## HTTPS and independent reverse-proxy authentication

After domain prerequisites and DNS are verified, allow inbound TCP 80 and 443.
Keep the app's direct 14242 access restricted while testing the proxy. On ECS:

```bash
sudo apt install -y nginx certbot python3-certbot-nginx apache2-utils
sudo mkdir -p /var/www/certbot
```

Render `deploy/nginx/ai-agent-http.conf.template`, replacing `__DOMAIN__` with
the real hostname and `__ADMIN_IP__` with the student's public `/32`. Install it
as `/etc/nginx/sites-available/ai-agent`, then enable it without removing any
existing site:

```bash
sudo ln -s /etc/nginx/sites-available/ai-agent /etc/nginx/sites-enabled/ai-agent
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d YOUR_REAL_DOMAIN
```

Create the proxy password file interactively. `-c` is for its first creation
only; omit it when adding a user to an existing file:

```bash
sudo htpasswd -c /etc/nginx/ai-agent.htpasswd learner
sudo chmod 640 /etc/nginx/ai-agent.htpasswd
sudo chown root:www-data /etc/nginx/ai-agent.htpasswd
```

Install `deploy/nginx/ai-agent-proxy.conf` as
`/etc/nginx/snippets/ai-agent-proxy.conf`. Render the final
`deploy/nginx/ai-agent.conf.template` with the real domain and replace only this
assignment site's configuration. Then check and reload Nginx. This configuration
authenticates every application request at Nginx, redirects HTTP to HTTPS, and
forwards the independent application Bearer token through a separate browser
header. The UI meta tag activates that transport; local usage remains compatible.

Set `AILA_BIND_ADDRESS=127.0.0.1` in ECS `.env`, recreate the service with the same
Compose project, and remove the public 14242 security-group rule. Recheck HTTPS
and verify that direct public-IP access to 14242 is blocked. Test both the proxy
login and the application's BNBU login, then generate a real artifact and open
its PDF preview. Capture successful access with the HTTPS address bar visible.

For repeatable checks, create a private owner-only netrc file outside the repo:

```text
machine YOUR_REAL_DOMAIN login YOUR_PROXY_USERNAME password YOUR_PROXY_PASSWORD
```

```bash
chmod 600 /path/to/private.netrc
bash scripts/check-https.sh YOUR_REAL_DOMAIN /path/to/private.netrc
sudo certbot renew --dry-run
systemctl list-timers | grep certbot
```

Keep credentials out of screenshots, shell histories, report excerpts, and Git.
Back up SQLite and workspace consistently, and back up the encryption master
key separately. A restart-persistence test should verify an existing account
and artifact after container recreation, without deleting the runtime volumes.

## Report and submission

Generate the report using the deployed app's Essay/PDF mode after evidence is
collected. Include all three tasks, real screenshots, commands and results,
architecture, security/cost tradeoffs, limitations, and improvements. Use the
student's name and ID supplied for this assignment. The revised prompt in
`backend/pipelines/essay_html.py` contains the report rubric. Verify the actual
PDF has no more than 20 pages and inspect every rendered page.

Submit the report, whole-project GitHub URL, `local-ui-check.txt`, and
`ecs-docker-check.txt`. Keep secrets, `.env*`, `data/`, `workspace/`, runtime
dependencies, caches, and generated app artifacts out of the source repository.

## Official references

- <https://help.aliyun.com/zh/acr/user-guide/create-a-container-registry-personal-edition-instance>
- <https://help.aliyun.com/zh/acr/user-guide/use-a-container-registry-personal-edition-instance-to-push-and-pull-images>
- <https://help.aliyun.com/zh/dws/user-guide/how-to-register-a-domain-name>
- <https://help.aliyun.com/zh/icp-filing/basic-icp-service/getting-started/quick-start-for-icp-filing-for-personal-websites>
- <https://platform.qianwenai.com/docs/developer-guides/getting-started/first-api-call>
- <https://nginx.org/en/docs/http/ngx_http_auth_basic_module.html>
- <https://eff-certbot.readthedocs.io/en/stable/using.html#nginx>
