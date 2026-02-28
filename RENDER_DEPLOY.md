# Redeploy Abjad Tailor using complete-abjada

Use [https://github.com/abdiwahaab12/complete-abjada](https://github.com/abdiwahaab12/complete-abjada) as the deployment source on Render.

## Step 1: Add render.yaml to complete-abjada (optional)

If you have write access to the repo:

1. Copy `render.yaml` from this project into the **root** of the complete-abjada repo
2. Commit and push:
   ```bash
   git clone https://github.com/abdiwahaab12/complete-abjada.git
   cd complete-abjada
   # copy render.yaml to repo root
   git add render.yaml
   git commit -m "Add Render blueprint"
   git push origin main
   ```

## Step 2: Connect Render to complete-abjada

### Option A: Deploy with Blueprint (if render.yaml is in the repo)

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **New** → **Blueprint**
3. Connect your GitHub account if needed
4. Select **abdiwahaab12/complete-abjada**
5. Render will detect `render.yaml` and create the web service
6. Add your **DATABASE_URL** (e.g. Railway MySQL):
   ```
   mysql+pymysql://USER:PASSWORD@HOST:PORT/DATABASE
   ```
7. Click **Apply**

### Option B: Manual Web Service (no render.yaml)

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **New** → **Web Service**
3. Connect **abdiwahaab12/complete-abjada**
4. Configure:
   - **Name**: abjad-tailor (or any name)
   - **Region**: Oregon (or nearest)
   - **Branch**: main
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1`
5. Add **Environment Variables**:
   - `DATABASE_URL` = your MySQL connection string (Railway MySQL)
   - `SECRET_KEY` = (generate or set a random string)
   - `JWT_SECRET_KEY` = (generate or set a random string)
6. Click **Create Web Service**

## Step 3: Database (Railway MySQL)

Ensure `DATABASE_URL` uses this format:

```
mysql+pymysql://USER:PASSWORD@HOST:PORT/DATABASE
```

Railway sometimes returns `mysql://`; change it to `mysql+pymysql://` for Python.

## Redeploy

After connecting:

- **Auto-deploy**: Every push to `main` triggers a new deploy
- **Manual redeploy**: Dashboard → your service → **Manual Deploy** → **Deploy latest commit**
