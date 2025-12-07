"""
Reconnaissance Agent - анализ UI веб-страниц
"""
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError
from typing import Dict, Any, List
import json
import time


class ReconnaissanceAgent:
    """Агент для анализа UI страниц"""
    
    def analyze_page(self, url: str, timeout: int = 60) -> Dict[str, Any]:
        """
        Анализ структуры веб-страницы
        
        Args:
            url: URL для анализа
            timeout: Таймаут загрузки страницы (секунды)
        
        Returns:
            Структура страницы с элементами
        """
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    context = browser.new_context(
                        viewport={"width": 1920, "height": 1080},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    )
                    page = context.new_page()
                    
                    # Навигация с ожиданием полной загрузки
                    page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
                    
                    # Извлечение структуры
                    page_structure = self._extract_page_structure(page, url)
                    
                    browser.close()
                    return page_structure
            
            except PlaywrightTimeoutError:
                if attempt < max_retries - 1:
                    time.sleep(2)  # Пауза перед retry
                    continue
                error_msg = f"Page load timeout after {max_retries} attempts for {url}"
                print(f"Reconnaissance error: {error_msg}")
                raise Exception(error_msg)
            
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                error_msg = f"Error analyzing page {url}: {str(e)}"
                print(f"Reconnaissance error: {error_msg}")
                import traceback
                traceback.print_exc()
                raise Exception(error_msg)
    
    def _extract_page_structure(self, page: Page, url: str) -> Dict[str, Any]:
        """Извлечение структуры элементов страницы"""
        
        # Получение базовой информации
        title = page.title()
        
        # Извлечение кнопок
        buttons = page.evaluate("""
            () => {
                const buttons = [];
                document.querySelectorAll('button, [role="button"], a[href]').forEach(btn => {
                    const text = btn.textContent?.trim() || '';
                    const selector = btn.getAttribute('data-testid') || 
                                   btn.getAttribute('id') || 
                                   btn.className;
                    if (text || selector) {
                        buttons.push({
                            text: text,
                            selector: selector || '',
                            visible: btn.offsetParent !== null
                        });
                    }
                });
                return buttons;
            }
        """)
        
        # Извлечение полей ввода
        inputs = page.evaluate("""
            () => {
                const inputs = [];
                document.querySelectorAll('input, textarea, select').forEach(input => {
                    inputs.push({
                        name: input.name || '',
                        type: input.type || input.tagName.toLowerCase(),
                        selector: input.getAttribute('data-testid') || input.id || input.name,
                        visible: input.offsetParent !== null
                    });
                });
                return inputs;
            }
        """)
        
        # Извлечение ссылок
        links = page.evaluate("""
            () => {
                const links = [];
                document.querySelectorAll('a[href]').forEach(link => {
                    links.push({
                        text: link.textContent?.trim() || '',
                        href: link.href,
                        visible: link.offsetParent !== null
                    });
                });
                return links;
            }
        """)
        
        # Генерация селекторов
        selectors = self._generate_selectors(page)
        
        return {
            "title": title,
            "url": url,
            "buttons": buttons[:50],  # Ограничение для производительности
            "inputs": inputs[:50],
            "links": links[:50],
            "selectors": selectors,
            "timestamp": time.time()
        }
    
    def _generate_selectors(self, page: Page) -> Dict[str, str]:
        """Генерация рекомендуемых селекторов"""
        selectors = {}
        
        # Поиск элементов с data-testid (приоритет 1)
        testid_elements = page.evaluate("""
            () => {
                const elements = {};
                document.querySelectorAll('[data-testid]').forEach(el => {
                    const testid = el.getAttribute('data-testid');
                    elements[testid] = `[data-testid="${testid}"]`;
                });
                return elements;
            }
        """)
        selectors.update(testid_elements)
        
        return selectors

