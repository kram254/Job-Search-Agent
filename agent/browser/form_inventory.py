import logging
from typing import List, Dict, Any


class FormInventory:

    @staticmethod
    def extract_inventory(browser) -> List[Dict[str, Any]]:
        try:
            page = browser.page
            fields = page.evaluate("""() => {
                const inventory = [];
                const seen = new Set();

                function getLabel(el) {
                    if (el.id) {
                        const lbl = document.querySelector(`label[for="${el.id}"]`);
                        if (lbl) return lbl.innerText.trim();
                    }
                    const parent = el.closest('label');
                    if (parent) return parent.innerText.trim();
                    const prev = el.previousElementSibling;
                    if (prev && prev.tagName === 'LABEL') return prev.innerText.trim();
                    const ariaLabel = el.getAttribute('aria-label');
                    if (ariaLabel) return ariaLabel.trim();
                    return el.placeholder || el.name || '';
                }

                function getOptions(el) {
                    if (el.tagName !== 'SELECT') return [];
                    return Array.from(el.options).map(o => ({
                        value: o.value,
                        text: o.text.trim()
                    }));
                }

                document.querySelectorAll('input, select, textarea').forEach(el => {
                    const key = el.id || el.name || el.type + '_' + el.offsetTop;
                    if (seen.has(key)) return;
                    seen.add(key);

                    const type = el.type || el.tagName.toLowerCase();
                    if (['hidden', 'button', 'submit', 'reset', 'image'].includes(type)) return;

                    inventory.push({
                        id: el.id || el.name || '',
                        name: el.name || el.id || '',
                        type: type,
                        label: getLabel(el),
                        placeholder: el.placeholder || '',
                        required: el.required || false,
                        value: el.value || '',
                        options: getOptions(el),
                        visible: el.offsetParent !== null
                    });
                });

                return inventory;
            }""")
            return fields or []
        except Exception as e:
            logging.warning(f"[FormInventory] DOM extraction failed: {e}")
            return [
                {"id": "first_name", "type": "text", "label": "First Name", "required": True, "options": []},
                {"id": "last_name", "type": "text", "label": "Last Name", "required": True, "options": []},
                {"id": "email", "type": "email", "label": "Email", "required": True, "options": []},
            ]
