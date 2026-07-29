function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * API请求封装函数
 * 自动添加X-API-Key请求头
 * @param {string} url - API端点URL
 * @param {object} options - fetch选项
 * @returns {Promise<Response>}
 */
async function apiRequest(url, options = {}) {
    // 获取存储的API密钥（从localStorage或页面配置）
    const apiKey = localStorage.getItem('apiKey') || window.apiKey || '';
    
    // 设置默认headers
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };
    
    // 如果有API密钥，添加到请求头
    if (apiKey) {
        headers['X-API-Key'] = apiKey;
    }
    
    // 合并选项
    const config = {
        ...options,
        headers,
    };
    
    // 如果有body，确保是JSON字符串
    if (config.body && typeof config.body === 'object') {
        config.body = JSON.stringify(config.body);
    }
    
    const response = await fetch(url, config);
    
    // 处理认证失败的情况
    if (response.status === 401 || response.status === 403) {
        const result = await response.json().catch(() => ({ error: '认证失败' }));
        // 清除无效的API密钥
        if (apiKey) {
            localStorage.removeItem('apiKey');
            window.apiKey = '';
        }
        // 提示用户重新输入API密钥
        const newKey = prompt('API密钥无效或未配置，请输入API密钥：');
        if (newKey) {
            localStorage.setItem('apiKey', newKey);
            window.apiKey = newKey;
            // 重新发起请求
            return apiRequest(url, options);
        }
        throw new Error(result.error || '认证失败');
    }
    
    return response;
}
