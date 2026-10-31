module.exports = {
  apps: [
    {
      name: "fb-property-bot",
      script: "main_bot.py",
      interpreter: "./venv/bin/python",
      autorestart: true,
      restart_delay: 10000, // jeda 10 detik sebelum auto-restart jika crash
      max_restarts: 50,
      watch: false,
      max_memory_restart: "1G",
      env: {
        PYTHONUNBUFFERED: "1",
        PYTHONIOENCODING: "utf-8"
      }
    }
  ]
};

