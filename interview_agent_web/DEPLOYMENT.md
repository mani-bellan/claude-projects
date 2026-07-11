# Deployment Guide - DE Interview Agent Swarm

This guide covers deploying your Next.js web app to various platforms, with Vercel being the recommended option.

## 🌐 Deployment Platforms

### 1. **Vercel** (Recommended) ⭐

Vercel is the official Next.js hosting platform. It offers:
- Zero-config deployments
- Automatic preview deploys on pull requests
- Built-in analytics and monitoring
- Global CDN
- Free tier with generous limits

#### Option A: GitHub Integration (Easiest)

1. **Push your code to GitHub**:
   ```bash
   git init
   git add .
   git commit -m "Initial commit: Interview Agent Web"
   git remote add origin https://github.com/yourusername/interview-agent-web.git
   git push -u origin main
   ```

2. **Deploy on Vercel**:
   - Go to [vercel.com](https://vercel.com/new)
   - Click "Continue with GitHub"
   - Select your `interview-agent-web` repository
   - Click "Import"

3. **Configure Environment Variables**:
   - In the "Environment Variables" section, add:
     ```
     NEXT_PUBLIC_GROQ_API_KEY = your_groq_api_key
     GROQ_API_KEY = your_groq_api_key
     ```
   - Click "Deploy"

4. **That's it!** Your app is now live at `your-project.vercel.app`

#### Option B: Vercel CLI

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel

# Follow prompts and set environment variables
# Deploy to production
vercel --prod
```

#### Option C: Docker Container

```bash
# Build Docker image
docker build -t interview-agent-web .

# Run locally
docker run -p 3000:3000 -e GROQ_API_KEY=your_key interview-agent-web

# Push to Docker Hub or container registry for cloud deployment
```

### 2. **Netlify**

```bash
# Install Netlify CLI
npm install -g netlify-cli

# Build the project
npm run build

# Deploy
netlify deploy --prod --dir=.next

# Or connect GitHub
# Go to netlify.com, click "New site from Git"
```

**Note**: Netlify has better support for serverless functions through Netlify Functions.

### 3. **AWS (Amplify/EC2/ECS)**

#### AWS Amplify (Easiest)

```bash
# Install Amplify CLI
npm install -g @aws-amplify/cli

# Configure
amplify configure

# Initialize and deploy
amplify init
amplify add hosting
amplify publish
```

#### AWS ECS (Docker)

```bash
# Create ECR repository
aws ecr create-repository --repository-name interview-agent-web

# Build and push
docker build -t interview-agent-web .
docker tag interview-agent-web:latest YOUR_ECR_URI:latest
docker push YOUR_ECR_URI:latest

# Deploy via ECS/Fargate
```

### 4. **Google Cloud Run**

```bash
# Build
npm run build

# Create Dockerfile
# Ensure Dockerfile exists

# Deploy
gcloud run deploy interview-agent-web \
  --source . \
  --platform managed \
  --region us-central1 \
  --set-env-vars GROQ_API_KEY=your_key
```

### 5. **Railway**

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up
```

### 6. **Render**

1. Go to [render.com](https://render.com)
2. Click "New" → "Web Service"
3. Connect your GitHub repository
4. Set build command: `npm install && npm run build`
5. Set start command: `npm start`
6. Add environment variables
7. Click "Create Web Service"

### 7. **DigitalOcean App Platform**

1. Go to [digitalocean.com/apps](https://www.digitalocean.com/products/app-platform)
2. Click "Create App"
3. Connect GitHub repository
4. Add environment variables
5. Deploy

## 📋 Pre-Deployment Checklist

- [ ] Test locally: `npm run dev`
- [ ] Run type check: `npm run type-check`
- [ ] Build production: `npm run build`
- [ ] Verify `.env.local` is in `.gitignore`
- [ ] Create `.env.example` with placeholder values
- [ ] Test with production build: `npm start`
- [ ] Update README with deployment instructions
- [ ] Set up error monitoring (optional: Sentry, LogRocket)

## 🔐 Environment Variables Checklist

For all platforms, ensure these are set:

```
NEXT_PUBLIC_GROQ_API_KEY=your_groq_key
GROQ_API_KEY=your_groq_key
```

Never commit `.env.local` to version control!

## 🚀 Post-Deployment

### 1. **Verify Deployment**
- Visit your deployed URL
- Test the full workflow:
  1. Set API key
  2. Select a category
  3. Enter a question
  4. Run the swarm
  5. Check results

### 2. **Set Up Monitoring**

#### Vercel Analytics
- Automatically included for all Vercel deployments
- Visit your project → "Analytics" tab

#### Sentry Error Tracking (Optional)
```bash
npm install @sentry/nextjs
```

See `sentry.config.js` setup guide.

#### Uptime Monitoring
- Use services like UptimeRobot or Pingdom
- Monitor your deployed URL

### 3. **Domain Setup**

#### On Vercel:
1. Go to project → "Settings" → "Domains"
2. Add your custom domain
3. Follow DNS setup instructions

#### Custom DNS:
- Point your domain's A record to your deployment
- Set up SSL certificate (usually automatic)

### 4. **CI/CD Pipeline**

#### GitHub Actions (Free)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Vercel

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm install
      - run: npm run type-check
      - run: npm run build
      - uses: vercel/action@v4
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
```

## 🐛 Troubleshooting

### "Build failed" error
```bash
# Clear build cache and rebuild
rm -rf .next node_modules
npm install
npm run build
```

### "Environment variables not set" error
- Verify environment variables in deployment platform settings
- Ensure variable names match exactly
- Redeploy after adding variables

### Slow cold starts
- This is normal for serverless functions
- Add caching headers in API responses
- Consider using a dedicated server (Railway, Render)

### API key errors
- Verify your Groq API key is valid
- Check the key hasn't expired
- Ensure the key has available API credits

## 📊 Performance Tips

1. **Enable compression**: Usually automatic on all platforms
2. **Use CDN**: Vercel provides this by default
3. **Database optimization**: N/A (no DB used currently)
4. **Image optimization**: Automatic with Next.js
5. **Code splitting**: Automatic with Next.js

## 💰 Cost Estimates

- **Vercel**: Free tier, Pro at $20/month
- **Netlify**: Free tier, Pro at $19/month
- **Railway**: Pay-as-you-go (usually $5-50/month)
- **Render**: Free tier, paid starting at $7/month
- **AWS**: Varies by usage (free tier available)
- **GCP**: Pay-as-you-go (free tier available)

## 🔄 Keeping Your Deployment Updated

```bash
# Pull latest changes
git pull origin main

# Update dependencies
npm update

# Rebuild and test
npm run build

# Deploy
vercel --prod  # or your deployment command
```

## 📞 Support

- **Vercel Documentation**: https://vercel.com/docs
- **Next.js Deployment**: https://nextjs.org/docs/deployment
- **GitHub Actions**: https://docs.github.com/en/actions

---

Happy deploying! 🚀
