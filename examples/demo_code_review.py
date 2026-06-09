"""用户管理系统 - 用于代码审查演示"""

import os
import sqlite3
import hashlib
import pickle
from typing import Any


# ===== 用户注册 =====

def register_user(username: str, password: str, email: str) -> dict:
    """注册新用户"""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # 问题1: SQL注入
    cursor.execute(f"SELECT * FROM users WHERE username = '{username}'")
    if cursor.fetchone():
        return {"error": "用户名已存在"}

    # 问题2: 明文存储密码
    cursor.execute(
        f"INSERT INTO users (username, password, email) VALUES ('{username}', '{password}', '{email}')"
    )
    conn.commit()
    conn.close()
    return {"status": "注册成功", "username": username}


# ===== 用户登录 =====

def login(username: str, password: str) -> dict:
    """用户登录"""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # 问题3: SQL注入 + 明文比对
    cursor.execute(f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'")
    user = cursor.fetchone()
    conn.close()

    if user:
        # 问题4: 用MD5做token，不安全
        token = hashlib.md5(f"{username}{password}".encode()).hexdigest()
        return {"status": "登录成功", "token": token}
    return {"error": "用户名或密码错误"}


# ===== 数据处理 =====

def process_user_data(data: Any) -> dict:
    """处理用户上传的数据"""
    # 问题5: 反序列化不可信数据，远程代码执行风险
    if isinstance(data, bytes):
        obj = pickle.loads(data)
        return {"processed": str(obj)}

    # 问题6: eval执行任意代码
    if isinstance(data, str):
        result = eval(data)
        return {"result": result}

    return {"error": "不支持的数据类型"}


# ===== 查询用户 =====

def get_all_users() -> list:
    """获取所有用户"""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # 问题7: SELECT * 暴露所有字段包括密码
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    conn.close()

    # 问题8: 没有分页，数据量大时内存爆炸
    return users


# ===== 文件操作 =====

def read_user_file(filename: str) -> str:
    """读取用户文件"""
    # 问题9: 路径穿越，可以读取任意文件
    filepath = f"/data/user_files/{filename}"
    with open(filepath, "r") as f:
        return f.read()


def delete_user(user_id: int) -> dict:
    """删除用户"""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # 问题10: 没有权限检查，任何人都能删
    cursor.execute(f"DELETE FROM users WHERE id = {user_id}")
    conn.commit()
    conn.close()

    # 问题11: 没有事务回滚，删除失败数据不一致
    return {"status": "已删除"}


# ===== 配置 =====

# 问题12: 硬编码密钥
SECRET_KEY = "my_super_secret_key_12345"
DATABASE_PASSWORD = "admin123"
API_ENDPOINT = "http://192.168.1.100:8080/api"


if __name__ == "__main__":
    # 问题13: 生产环境开了debug
    import logging
    logging.basicConfig(level=logging.DEBUG)
    print("Server starting with DEBUG mode...")
