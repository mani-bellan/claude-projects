# ⚡ Quick Start Guide

Get your DE Interview Agent Swarm running in 5 minutes!

## 🚀 Option 1: Local Development (Fastest)

### Prerequisites
- Node.js 18+ installed
- npm or yarn

### Steps

1. **Install dependencies**
   ```bash
   npm install
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env.local
   ```

3. **Get your Groq API Key**
   - Visit https://console.groq.com
   - Sign up (free)
   - Create an API key
   - Copy it to `.env.local`:
     ```
     NEXT_PUBLIC_GROQ_API_KEY=gsk_your_key_here
     ```

4. **Start dev server**
   ```bash
   npm run dev
   ```

5. **Open browser**
   - Navigate to http://localhost:3000
   - You're done! 🎉

## 🐳 Option 2: Docker (No Node.js needed)

### Prerequisites
- Docker installed

### Steps

1. **Create environment file**
   ```bash
   cp .env.example .env
   ```

2. **Add your Groq API key to `.env`**

3. **Start with Docker Compose**
   ```bash
   docker-compose up
   ```

4. **Open browser**
   - Navigate to http://localhost:3000

## ☁️ Option 3: Deploy to Vercel (Free Hosting)

### Prerequisites
- GitHub account
- Groq API key

### Steps

1. **Fork this repository on GitHub**
   (or push your local copy)

2. **Deploy on Vercel**
   - Go to https://vercel.com/new
   - Click "Continue with GitHub"
   - Select your repository
   - Click "Import"

3. **Add environment variables**
   - In the "Environment Variables" section:
     ```
     NEXT_PUBLIC_GROQ_API_KEY = your_groq_key
     GROQ_API_KEY = your_groq_key
     ```

4. **Click "Deploy"**
   - Wait for build to complete
   - Your app is live! 🌐

## 📖 Usage

### First Time
1. Click the ⚙ button → "Set API Key"
2. Paste your Groq API key
3. Click "Save"

### Run Interview
1. Choose a **Category** (Coding, Architecture, etc.)
2. Click an **Example** or type your question
3. Click **"▶ Run Swarm"**
4. Watch agents process your question
5. Review the **Final Solution**
6. Click **"⬇ Save Markdown"** to export

## 🔗 Useful Links

- **Groq Console**: https://console.groq.com
- **Groq Docs**: https://console.groq.com/docs
- **Next.js Docs**: https://nextjs.org/docs
- **Vercel Docs**: https://vercel.com/docs
- **Tailwind CSS**: https://tailwindcss.com

## ⚙️ Available Commands

```bash
npm run dev           # Start development server
npm run build        # Build for production
npm start            # Start production server
npm run lint         # Run ESLint
npm run type-check   # Check TypeScript
```

## 🆘 Troubleshooting

### "API key is required" error
- ✅ Set your Groq API key in settings (⚙ button)
- ✅ Make sure it starts with `gsk_`
- ✅ Check the key at https://console.groq.com

### "Connection error" or "Cannot reach API"
- ✅ Check your internet connection
- ✅ Verify your API key is valid
- ✅ Check if Groq API is experiencing issues

### Port 3000 already in use
```bash
# On macOS/Linux
lsof -i :3000
kill -9 <PID>

# On Windows
netstat -ano | findstr :3000
taskkill /PID <PID> /F
```

### Node modules issues
```bash
rm -rf node_modules package-lock.json
npm install
```

## 🎓 What's Happening?

The app uses a 4-agent pipeline:

1. **📖 Reader**: Analyzes your question
2. **💡 Solver**: Creates initial solution
3. **✓ Validator**: Checks for issues
4. **⚡ Optimizer**: Finalizes & optimizes

Each agent uses Groq's Llama 3.3 70B model for top-quality responses.

## 📚 Learn More

- Full documentation: See `README.md`
- Deployment guide: See `DEPLOYMENT.md`
- Original Python version: Check the `interview_helper.py` in parent directory

## 🎯 Next Steps

- [ ] Run your first interview question
- [ ] Export a solution as Markdown
- [ ] Try different categories
- [ ] Deploy to Vercel
- [ ] Share with friends!

---

**Happy interviewing!** 🚀

Questions? Check the troubleshooting section or open an issue on GitHub.
