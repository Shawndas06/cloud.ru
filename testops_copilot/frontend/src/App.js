export default function App() {
    return `
        <div class="app">
            <header class="header">
                <div class="header-content">
                    <h1>🤖 TestOps Copilot</h1>
                    <p>AI Assistant для автоматической генерации тест-кейсов</p>
                </div>
            </header>

            <main class="main-content">
                <div class="tabs">
                    <button class="tab active" data-tab="generate">🚀 Генерация тестов</button>
                    <button class="tab" data-tab="test-plan">📋 Тест-планы</button>
                    <button class="tab" data-tab="integrations">🔗 Интеграции</button>
                    <button class="tab" data-tab="optimize">⚡ Оптимизация</button>
                    <button class="tab" data-tab="validate">✅ Валидация</button>
                </div>

                <!-- Генерация тестов -->
                <div id="generate" class="tab-content active">
                    <div class="card">
                        <h2>Генерация UI тест-кейсов</h2>
                        <form id="generateForm">
                            <div class="form-group">
                                <label>🌐 URL для тестирования:</label>
                                <input type="url" id="testUrl" placeholder="https://cloud.ru/calculator" required>
                            </div>
                            <div class="form-group">
                                <label>📝 Требования:</label>
                                <div id="requirementsList" class="requirements-list">
                                    <div class="requirement-item">
                                        <input type="text" class="requirement-input" placeholder="Введите требование" required>
                                        <button type="button" class="btn-remove" onclick="this.parentElement.remove()">✕</button>
                                    </div>
                                </div>
                                <button type="button" id="addRequirement" class="btn-secondary">+ Добавить требование</button>
                            </div>
                            <div class="form-group">
                                <label>🎯 Тип тестов:</label>
                                <select id="testType">
                                    <option value="both">Ручные и автоматизированные</option>
                                    <option value="automated">Только автоматизированные</option>
                                    <option value="manual">Только ручные</option>
                                </select>
                            </div>
                            <button type="submit" id="generateBtn" class="btn-primary">🚀 Сгенерировать тесты</button>
                        </form>
                        <div id="generateResult" class="result"></div>
                    </div>
                </div>

                <!-- Тест-планы -->
                <div id="test-plan" class="tab-content">
                    <div class="card">
                        <h2>Генерация тест-плана</h2>
                        <form id="testPlanForm">
                            <div class="form-group">
                                <label>📝 Требования:</label>
                                <div id="testPlanRequirementsList" class="requirements-list">
                                    <div class="requirement-item">
                                        <input type="text" class="requirement-input" placeholder="Введите требование" required>
                                        <button type="button" class="btn-remove" onclick="this.parentElement.remove()">✕</button>
                                    </div>
                                </div>
                                <button type="button" id="addTestPlanRequirement" class="btn-secondary">+ Добавить требование</button>
                            </div>
                            <div class="form-group">
                                <label>🔑 Ключ проекта (опционально):</label>
                                <input type="text" id="projectKey" placeholder="PROJECT-KEY">
                                <small>Для анализа дефектов из Jira/Allure TestOps</small>
                            </div>
                            <button type="submit" id="testPlanBtn" class="btn-primary">📋 Сгенерировать тест-план</button>
                        </form>
                        <div id="testPlanResult" class="result"></div>
                    </div>
                </div>

                <!-- Интеграции -->
                <div id="integrations" class="tab-content">
                    <div class="card">
                        <h2>Проверка интеграций</h2>
                        <div class="button-group">
                            <button id="testIntegrationsBtn" class="btn-primary">🔍 Проверить подключения</button>
                            <button id="configStatusBtn" class="btn-secondary">⚙️ Статус конфигурации</button>
                        </div>
                        <div id="integrationsResult" class="result"></div>
                    </div>
                </div>

                <!-- Оптимизация -->
                <div id="optimize" class="tab-content">
                    <div class="card">
                        <h2>Оптимизация тестов</h2>
                        <p class="info-text">Функционал оптимизации доступен через API. Используйте endpoint:</p>
                        <code>POST /api/v1/optimize/tests</code>
                        <div class="result" style="margin-top: 20px;">
                            <div class="status info">
                                💡 Для оптимизации отправьте POST запрос с тестами и требованиями
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Валидация -->
                <div id="validate" class="tab-content">
                    <div class="card">
                        <h2>Валидация тестов</h2>
                        <p class="info-text">Функционал валидации доступен через API. Используйте endpoint:</p>
                        <code>POST /api/v1/validate/tests</code>
                        <div class="result" style="margin-top: 20px;">
                            <div class="status info">
                                💡 Для валидации отправьте POST запрос с тестами для проверки
                            </div>
                        </div>
                    </div>
                </div>
            </main>

            <footer class="footer">
                <p>TestOps Copilot v1.0.0 | API: <a href="http://localhost:8000/docs" target="_blank">/docs</a></p>
            </footer>
        </div>
    `
}

