@echo off
REM Windows 任务计划程序示例：每日凌晨 2 点执行此脚本
cd /d "%~dp0.."
call python scripts\backup_database.py --dir backups
if errorlevel 1 exit /b 1
echo Backup OK at %date% %time%
