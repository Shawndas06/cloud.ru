import './style.css'
import App from './App.js'

document.querySelector('#app').innerHTML = App()

// Инициализация после загрузки DOM
document.addEventListener('DOMContentLoaded', () => {
    initializeApp()
})

function initializeApp() {
    // Переключение вкладок
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            const tabName = e.target.dataset.tab
            switchTab(tabName)
        })
    })

    // Формы
    setupGenerateForm()
    setupTestPlanForm()
    setupIntegrations()
}

function switchTab(tabName) {
    // Скрыть все табы
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'))
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'))
    
    // Показать выбранный
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active')
    document.getElementById(tabName).classList.add('active')
}

function setupGenerateForm() {
    const form = document.getElementById('generateForm')
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault()
            await generateTests()
        })
    }
    
    // Добавление требований
    const addBtn = document.getElementById('addRequirement')
    if (addBtn) {
        addBtn.addEventListener('click', addRequirement)
    }
}

function setupTestPlanForm() {
    const form = document.getElementById('testPlanForm')
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault()
            await generateTestPlan()
        })
    }
    
    const addBtn = document.getElementById('addTestPlanRequirement')
    if (addBtn) {
        addBtn.addEventListener('click', addTestPlanRequirement)
    }
}

function setupIntegrations() {
    const testBtn = document.getElementById('testIntegrationsBtn')
    if (testBtn) {
        testBtn.addEventListener('click', testIntegrations)
    }
    
    const configBtn = document.getElementById('configStatusBtn')
    if (configBtn) {
        configBtn.addEventListener('click', getConfigStatus)
    }
}

function addRequirement() {
    const container = document.getElementById('requirementsList')
    const div = document.createElement('div')
    div.className = 'requirement-item'
    div.innerHTML = `
        <input type="text" class="requirement-input" placeholder="Введите требование" required>
        <button type="button" class="btn-remove" onclick="this.parentElement.remove()">✕</button>
    `
    container.appendChild(div)
}

function addTestPlanRequirement() {
    const container = document.getElementById('testPlanRequirementsList')
    const div = document.createElement('div')
    div.className = 'requirement-item'
    div.innerHTML = `
        <input type="text" class="requirement-input" placeholder="Введите требование" required>
        <button type="button" class="btn-remove" onclick="this.parentElement.remove()">✕</button>
    `
    container.appendChild(div)
}

function getRequirements(containerId) {
    const inputs = document.querySelectorAll(`#${containerId} .requirement-input`)
    return Array.from(inputs).map(input => input.value.trim()).filter(v => v)
}

async function generateTests() {
    const btn = document.getElementById('generateBtn')
    const resultDiv = document.getElementById('generateResult')
    
    btn.disabled = true
    btn.innerHTML = '<span class="spinner"></span> Генерация...'
    resultDiv.classList.remove('show')
    resultDiv.innerHTML = ''

    const url = document.getElementById('testUrl').value
    const requirements = getRequirements('requirementsList')
    const testType = document.getElementById('testType').value

    try {
        const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8000/api/v1' : '/api/v1'
        const response = await fetch(`${API_BASE}/generate/test-cases`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: url,
                requirements: requirements,
                test_type: testType
            })
        })

        const data = await response.json()

        if (response.ok) {
            resultDiv.innerHTML = `
                <div class="status success">✅ Задача создана успешно!</div>
                <div class="result-content">
                    <h3>Результат:</h3>
                    <div class="info-grid">
                        <div><strong>Request ID:</strong> ${data.request_id}</div>
                        <div><strong>Task ID:</strong> ${data.task_id}</div>
                        <div><strong>Статус:</strong> ${data.status}</div>
                        <div><a href="${data.stream_url}" target="_blank">📊 Отслеживать прогресс</a></div>
                    </div>
                    <pre>${JSON.stringify(data, null, 2)}</pre>
                </div>
            `
        } else {
            resultDiv.innerHTML = `
                <div class="status error">❌ Ошибка: ${data.detail || 'Неизвестная ошибка'}</div>
                <pre>${JSON.stringify(data, null, 2)}</pre>
            `
        }
    } catch (error) {
        resultDiv.innerHTML = `
            <div class="status error">❌ Ошибка подключения: ${error.message}</div>
            <p>Убедитесь, что API Gateway запущен на http://localhost:8000</p>
        `
    } finally {
        btn.disabled = false
        btn.innerHTML = '🚀 Сгенерировать тесты'
        resultDiv.classList.add('show')
    }
}

async function generateTestPlan() {
    const btn = document.getElementById('testPlanBtn')
    const resultDiv = document.getElementById('testPlanResult')
    
    btn.disabled = true
    btn.innerHTML = '<span class="spinner"></span> Генерация...'
    resultDiv.classList.remove('show')
    resultDiv.innerHTML = ''

    const requirements = getRequirements('testPlanRequirementsList')
    const projectKey = document.getElementById('projectKey').value || null

    try {
        const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8000/api/v1' : '/api/v1'
        const response = await fetch(`${API_BASE}/test-plan/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                requirements: requirements,
                project_key: projectKey,
                days_back: 90
            })
        })

        const data = await response.json()

        if (response.ok) {
            const testPlan = data.test_plan
            resultDiv.innerHTML = `
                <div class="status success">✅ Тест-план сгенерирован!</div>
                <div class="result-content">
                    <h3>${testPlan.title || 'Тест-план'}</h3>
                    <p><strong>Описание:</strong> ${testPlan.description || 'Нет описания'}</p>
                    <p><strong>Тест-кейсов:</strong> ${testPlan.test_cases?.length || 0}</p>
                    <div class="test-cases-list">
                        ${(testPlan.test_cases || []).slice(0, 10).map((tc, i) => `
                            <div class="test-case-card">
                                <div class="test-case-header">
                                    <span class="test-id">${tc.id || `TC-${i+1}`}</span>
                                    <span class="priority priority-${tc.priority || 5}">Приоритет: ${tc.priority || 5}</span>
                                </div>
                                <h4>${tc.name || 'Без названия'}</h4>
                                <p>${tc.description || ''}</p>
                                <div class="test-case-meta">
                                    <span>Компонент: ${tc.component || 'N/A'}</span>
                                    <span>Тип: ${tc.test_type || 'functional'}</span>
                                    <span>Время: ${tc.estimated_time || 'N/A'}</span>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                    ${data.defect_analysis ? `
                        <details class="defect-analysis">
                            <summary>📊 Анализ дефектов</summary>
                            <pre>${JSON.stringify(data.defect_analysis, null, 2)}</pre>
                        </details>
                    ` : ''}
                </div>
            `
        } else {
            resultDiv.innerHTML = `
                <div class="status error">❌ Ошибка: ${data.detail || 'Неизвестная ошибка'}</div>
                <pre>${JSON.stringify(data, null, 2)}</pre>
            `
        }
    } catch (error) {
        resultDiv.innerHTML = `
            <div class="status error">❌ Ошибка подключения: ${error.message}</div>
            <p>Убедитесь, что API Gateway запущен на http://localhost:8000</p>
        `
    } finally {
        btn.disabled = false
        btn.innerHTML = '📋 Сгенерировать тест-план'
        resultDiv.classList.add('show')
    }
}

async function testIntegrations() {
    const resultDiv = document.getElementById('integrationsResult')
    resultDiv.classList.remove('show')
    resultDiv.innerHTML = '<div class="status info">⏳ Проверка подключений...</div>'
    resultDiv.classList.add('show')

    try {
        const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8000/api/v1' : '/api/v1'
        const response = await fetch(`${API_BASE}/integrations/test-connection?source=all`)
        const data = await response.json()

        let html = '<h3>Результаты проверки:</h3>'
        
        if (data.jira.connected) {
            html += `
                <div class="status success">
                    ✅ Jira: Подключено
                    ${data.jira.user ? `<br>👤 Пользователь: ${data.jira.user}` : ''}
                    ${data.jira.email ? `<br>📧 Email: ${data.jira.email}` : ''}
                </div>
            `
        } else {
            html += `
                <div class="status error">
                    ❌ Jira: Не подключено
                    ${data.jira.error ? `<br>⚠️ Ошибка: ${data.jira.error}` : ''}
                </div>
            `
        }

        if (data.allure.connected) {
            html += `
                <div class="status success">
                    ✅ Allure TestOps: Подключено
                </div>
            `
        } else {
            html += `
                <div class="status error">
                    ❌ Allure TestOps: Не подключено
                    ${data.allure.error ? `<br>⚠️ Ошибка: ${data.allure.error}` : ''}
                </div>
            `
        }

        html += `<details class="details-json"><summary>📄 Полный ответ</summary><pre>${JSON.stringify(data, null, 2)}</pre></details>`
        resultDiv.innerHTML = html
    } catch (error) {
        resultDiv.innerHTML = `
            <div class="status error">❌ Ошибка подключения: ${error.message}</div>
            <p>Убедитесь, что API Gateway запущен на http://localhost:8000</p>
        `
    }
}

async function getConfigStatus() {
    const resultDiv = document.getElementById('integrationsResult')
    resultDiv.classList.remove('show')
    resultDiv.innerHTML = '<div class="status info">⏳ Получение статуса...</div>'
    resultDiv.classList.add('show')

    try {
        const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8000/api/v1' : '/api/v1'
        const response = await fetch(`${API_BASE}/integrations/configuration-status`)
        const data = await response.json()

        let html = '<h3>Статус конфигурации:</h3>'
        
        const jira = data.configuration.jira
        html += `
            <div class="status ${jira.url_configured && jira.auth_configured ? 'success' : 'error'}">
                <strong>Jira:</strong>
                ${jira.url_configured ? '✅ URL' : '❌ URL'}
                ${jira.auth_configured ? '✅ Auth' : '❌ Auth'}
                ${jira.auth_type ? `<br>Тип аутентификации: ${jira.auth_type}` : ''}
            </div>
        `

        const allure = data.configuration.allure
        html += `
            <div class="status ${allure.url_configured && allure.token_configured ? 'success' : 'error'}">
                <strong>Allure TestOps:</strong>
                ${allure.url_configured ? '✅ URL' : '❌ URL'}
                ${allure.token_configured ? '✅ Token' : '❌ Token'}
            </div>
        `

        if (data.instructions) {
            html += `<div class="instructions"><h4>📋 Инструкции:</h4>`
            if (data.instructions.jira) {
                html += `<div class="instruction-block"><strong>Jira:</strong><ul>`
                data.instructions.jira.auth_options.forEach(opt => {
                    html += `<li>${opt}</li>`
                })
                html += `</ul><p>${data.instructions.jira.how_to_get_token}</p></div>`
            }
            if (data.instructions.allure) {
                html += `<div class="instruction-block"><strong>Allure TestOps:</strong><p>${data.instructions.allure.how_to_get_token}</p></div>`
            }
            html += `</div>`
        }

        html += `<details class="details-json"><summary>📄 Полный ответ</summary><pre>${JSON.stringify(data, null, 2)}</pre></details>`
        resultDiv.innerHTML = html
    } catch (error) {
        resultDiv.innerHTML = `
            <div class="status error">❌ Ошибка подключения: ${error.message}</div>
            <p>Убедитесь, что API Gateway запущен на http://localhost:8000</p>
        `
    }
}

// Экспорт для глобального использования
window.addRequirement = addRequirement
window.addTestPlanRequirement = addTestPlanRequirement

