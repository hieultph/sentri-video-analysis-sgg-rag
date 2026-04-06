# 🐍 Sentri with Conda Environment

## Quick Start with Conda

### Step 1: Activate Conda Environment

```powershell
conda activate agno-env
```

### Step 2: Install bcrypt (if needed)

```powershell
pip install bcrypt
```

### Step 3: Test the System

```powershell
python test_sentri.py
```

### Step 4: Start Server

```powershell
python app.py
```

Or simply double-click: **start_sentri.bat** (it will activate conda automatically)

---

## 🔧 Complete Setup with Conda

```powershell
# Activate environment
conda activate agno-env

# Install bcrypt if needed
pip install bcrypt

# Verify installation
python -c "import bcrypt; print('bcrypt installed:', bcrypt.__version__)"

# Test system
python test_sentri.py

# Initialize database
python db_setup.py

# Start server
python app.py
```

---

## 🌐 Access the System

Once the server starts, open your browser:

- **Register**: http://localhost:7777/static/register.html
- **Login**: http://localhost:7777/static/login.html
- **Dashboard**: http://localhost:7777/static/index.html (after login)

---

## 📝 All Commands Should Use Conda

**ALWAYS activate conda environment first:**

```powershell
conda activate agno-env
```

Then run any command:

```powershell
python test_sentri.py
python db_setup.py
python app.py
```

---

## 🚀 Easiest Method

Just double-click: **start_sentri.bat**

It automatically:

1. ✅ Activates conda environment 'agno-env'
2. ✅ Checks Python installation
3. ✅ Installs bcrypt if needed
4. ✅ Initializes database
5. ✅ Starts the server

---

## ⚠️ Important Note

All Python packages should be installed in the **agno-env** conda environment, not globally.

Always use:

```powershell
conda activate agno-env
pip install <package>
```
