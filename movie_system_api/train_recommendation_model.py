# [file name]: train_recommendation_model.py
import schedule
import time
from datetime import datetime
from models.recommendation_model import recommender
import logging
import os

# 确保 logs 目录存在
os.makedirs('logs', exist_ok=True)

# 确保 models_storage 目录存在
os.makedirs('models_storage', exist_ok=True)

# 然后继续原来的配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/recommendation_training.log'),
        logging.StreamHandler()
    ]
)
def train_model():
    """训练推荐模型"""
    logging.info("开始训练推荐模型...")
    start_time = datetime.now()

    try:
        success = recommender.train_hybrid_model()

        if success:
            training_time = datetime.now() - start_time
            logging.info(f"模型训练成功！耗时: {training_time}")
        else:
            logging.error("模型训练失败")

    except Exception as e:
        logging.error(f"训练过程中发生错误: {e}")


def scheduled_training():
    """定时训练"""
    logging.info("启动定时训练任务...")

    # 每天凌晨3点训练一次
    schedule.every().day.at("03:00").do(train_model)

    # 立即训练一次
    train_model()

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    print("推荐模型训练脚本")
    print("1. 立即训练")
    print("2. 启动定时训练")

    choice = input("请选择 (1/2): ").strip()

    if choice == "1":
        train_model()
    elif choice == "2":
        scheduled_training()
    else:
        train_model()