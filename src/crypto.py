"""
加密工具模块
提供API密钥等敏感信息的加密/解密功能

使用AES-GCM模式进行加密，提供认证加密（AEAD）
"""
import os
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag

# 默认加密密钥环境变量名
ENCRYPTION_KEY_ENV = "ENCRYPTION_KEY"

# AES-GCM需要12字节的nonce
NONCE_SIZE = 12

# AES密钥长度（256位 = 32字节）
KEY_SIZE = 32


def _get_encryption_key() -> bytes:
    """
    获取加密密钥
    
    从环境变量ENCRYPTION_KEY读取，若未配置则生成警告并使用默认密钥（仅用于开发环境）
    生产环境必须配置ENCRYPTION_KEY环境变量
    """
    key = os.environ.get(ENCRYPTION_KEY_ENV, "")
    
    if not key:
        # 开发环境默认密钥（仅用于测试，生产环境必须设置）
        import warnings
        warnings.warn(
            f"ENCRYPTION_KEY环境变量未配置，使用开发环境默认密钥！"
            f"生产环境必须设置{ENCRYPTION_KEY_ENV}环境变量",
            UserWarning
        )
        # 使用固定的开发环境密钥（Base64编码）
        default_key_b64 = "your_development_encryption_key_must_be_32_bytes_long!!"
        return default_key_b64[:KEY_SIZE].encode('utf-8')
    
    # 支持Base64编码的密钥
    try:
        decoded_key = base64.b64decode(key)
        if len(decoded_key) == KEY_SIZE:
            return decoded_key
    except Exception:
        pass
    
    # 如果不是Base64，直接使用字符串（取前32字节）
    return key[:KEY_SIZE].encode('utf-8')


def encrypt(data: str) -> str:
    """
    加密字符串
    
    Args:
        data: 要加密的字符串
        
    Returns:
        加密后的Base64编码字符串
    """
    if not data:
        return ""
    
    key = _get_encryption_key()
    nonce = os.urandom(NONCE_SIZE)
    
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce), backend=default_backend())
    encryptor = cipher.encryptor()
    
    # 加密数据
    ciphertext = encryptor.update(data.encode('utf-8')) + encryptor.finalize()
    
    # 返回格式: nonce + tag + ciphertext（全部Base64编码）
    combined = nonce + encryptor.tag + ciphertext
    return base64.b64encode(combined).decode('utf-8')


def decrypt(encrypted_data: str) -> str:
    """
    解密字符串
    
    Args:
        encrypted_data: 加密后的Base64编码字符串
        
    Returns:
        解密后的原始字符串
    """
    if not encrypted_data:
        return ""
    
    key = _get_encryption_key()
    
    try:
        combined = base64.b64decode(encrypted_data)
        
        # 分离nonce、tag和ciphertext
        nonce = combined[:NONCE_SIZE]
        tag = combined[NONCE_SIZE:NONCE_SIZE + 16]  # GCM tag是16字节
        ciphertext = combined[NONCE_SIZE + 16:]
        
        cipher = Cipher(algorithms.AES(key), modes.GCM(nonce, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        return plaintext.decode('utf-8')
    
    except (ValueError, InvalidTag) as e:
        # 解密失败，可能是密钥不匹配或数据损坏
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"解密失败: {e}")
        # 返回原始数据（兼容旧数据）
        return encrypted_data


def generate_encryption_key() -> str:
    """
    生成一个新的加密密钥
    
    Returns:
        Base64编码的密钥字符串
    """
    key = os.urandom(KEY_SIZE)
    return base64.b64encode(key).decode('utf-8')


# 测试
if __name__ == "__main__":
    # 生成测试密钥
    test_key = generate_encryption_key()
    print(f"生成的加密密钥: {test_key}")
    
    # 设置环境变量测试
    os.environ[ENCRYPTION_KEY_ENV] = test_key
    
    # 测试加密解密
    test_data = "sk-1234567890abcdefghijklmnopqrstuvwxyz"
    encrypted = encrypt(test_data)
    print(f"原始数据: {test_data}")
    print(f"加密后: {encrypted}")
    
    decrypted = decrypt(encrypted)
    print(f"解密后: {decrypted}")
    
    assert decrypted == test_data, "加密解密不一致！"
    print("\n✅ 加密解密测试通过！")
