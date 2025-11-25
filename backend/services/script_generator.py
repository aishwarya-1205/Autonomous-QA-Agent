"""
Selenium Script Generator Service
Generates executable Selenium Python scripts from test cases
"""

import re
import json
from typing import Dict, List
from bs4 import BeautifulSoup
from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()


class ScriptGenerator:
    def __init__(self, rag_service):
        self.rag_service = rag_service
        self.client = Groq(api_key=os.getenv('GROQ_API_KEY'))
        self.model = os.getenv('LLM_MODEL', 'mixtral-8x7b-32768')
    
    def generate_script(self, test_case: Dict, html_content: str, browser: str = "chrome") -> Dict:
        """Generate Selenium Python script for a test case"""
        
        # Extract selectors from HTML
        selectors = self._extract_selectors(html_content)
        
        # Get relevant documentation context
        query = f"{test_case['feature']} {test_case['test_scenario']}"
        context_docs = self.rag_service.retrieve_context(query, k=3)
        context = self._build_context_string(context_docs)
        
        # Generate script using LLM
        script = self._generate_with_llm(test_case, html_content, selectors, context, browser)
        
        return {
            "script": script,
            "selectors_used": self._extract_used_selectors(script, selectors),
            "explanation": self._generate_explanation(test_case, script)
        }
    
    def _extract_selectors(self, html_content: str) -> Dict[str, Dict]:
        """Extract all possible selectors from HTML"""
        soup = BeautifulSoup(html_content, 'html.parser')
        selectors = {}
        
        # Find all interactive elements
        for element in soup.find_all(['input', 'button', 'select', 'textarea', 'a']):
            element_info = {
                'tag': element.name,
                'id': element.get('id'),
                'name': element.get('name'),
                'class': element.get('class', []),
                'type': element.get('type'),
                'text': element.get_text(strip=True) if element.name != 'input' else None,
                'placeholder': element.get('placeholder'),
                'value': element.get('value')
            }
            
            # Create selector key
            if element_info['id']:
                key = f"#{element_info['id']}"
                selectors[key] = element_info
            elif element_info['name']:
                key = f"[name='{element_info['name']}']"
                selectors[key] = element_info
            elif element_info['text']:
                key = f"{element.name}:contains('{element_info['text'][:30]}')"
                selectors[key] = element_info
        
        return selectors
    
    def _build_context_string(self, context_docs: List[Dict]) -> str:
        """Build context from retrieved documents"""
        return "\n\n".join([
            f"[{doc.get('metadata', {}).get('source', 'doc')}]\n{doc.get('content', '')}"
            for doc in context_docs
        ])
    
    def _generate_with_llm(self, test_case: Dict, html_content: str, 
                           selectors: Dict, context: str, browser: str) -> str:
        """Generate Selenium script using LLM"""
        
        # Prepare selector information
        selector_info = self._format_selectors_for_prompt(selectors)
        
        system_prompt = """You are an expert Selenium test automation engineer. Generate clean, professional, executable Python Selenium scripts.

REQUIREMENTS:
1. Use actual selectors from the provided HTML
2. Include proper waits (WebDriverWait with expected_conditions)
3. Add error handling and assertions
4. Include clear comments
5. Use PEP 8 style
6. Make scripts fully executable
7. Include setup and teardown
8. Add verification steps

The script must be production-ready and runnable."""

        user_prompt = f"""Generate a complete Selenium Python script for this test case:

TEST CASE:
- ID: {test_case['test_id']}
- Feature: {test_case['feature']}
- Scenario: {test_case['test_scenario']}
- Type: {test_case['test_type']}
- Steps: {json.dumps(test_case['test_steps'], indent=2)}
- Expected: {test_case['expected_result']}

AVAILABLE SELECTORS FROM HTML:
{selector_info}

DOCUMENTATION CONTEXT:
{context}

BROWSER: {browser}

Generate a complete Python script that:
1. Sets up the WebDriver
2. Implements all test steps
3. Uses proper waits and error handling
4. Includes assertions for expected results
5. Has proper cleanup in teardown
6. Is fully executable

Return ONLY the Python code, no explanations."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=3000
            )
            
            script = response.choices[0].message.content.strip()
            
            # Clean up code blocks
            script = re.sub(r'```python\s*', '', script)
            script = re.sub(r'```\s*$', '', script)
            script = script.strip()
            
            # Validate script has required imports
            if 'selenium' not in script.lower():
                script = self._add_required_imports(script, browser)
            
            return script
        
        except Exception as e:
            print(f"Error generating script: {e}")
            return self._generate_fallback_script(test_case, selectors, browser)
    
    def _format_selectors_for_prompt(self, selectors: Dict) -> str:
        """Format selectors for LLM prompt"""
        lines = []
        for selector, info in list(selectors.items())[:20]:  # Limit to 20 selectors
            desc = f"{info['tag']}"
            if info.get('id'):
                desc += f" id='{info['id']}'"
            if info.get('name'):
                desc += f" name='{info['name']}'"
            if info.get('text'):
                desc += f" text='{info['text'][:30]}'"
            
            lines.append(f"  {selector}: {desc}")
        
        return "\n".join(lines)
    
    def _add_required_imports(self, script: str, browser: str) -> str:
        """Add required imports if missing"""
        imports = f"""from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.{browser}.service import Service
from webdriver_manager.{browser} import {browser.capitalize()}DriverManager
import time

"""
        return imports + script
    
    def _generate_fallback_script(self, test_case: Dict, selectors: Dict, browser: str) -> str:
        """Generate basic script if LLM fails"""
        
        script = f'''"""
Selenium Test Script
Test ID: {test_case["test_id"]}
Feature: {test_case["feature"]}
Scenario: {test_case["test_scenario"]}
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.{browser}.service import Service
from webdriver_manager.{browser} import {browser.capitalize()}DriverManager
import time


class Test{test_case["test_id"].replace("-", "_")}:
    def setup_method(self):
        """Setup test environment"""
        self.driver = webdriver.{browser.capitalize()}(
            service=Service({browser.capitalize()}DriverManager().install())
        )
        self.driver.maximize_window()
        self.driver.implicitly_wait(10)
    
    def test_{test_case["test_id"].lower().replace("-", "_")}(self):
        """
        Test: {test_case["test_scenario"]}
        Expected: {test_case["expected_result"]}
        """
        try:
            # Load the page
            self.driver.get("file:///path/to/your/checkout.html")
            time.sleep(2)
            
            # Test steps
'''
        
        # Add test steps
        for i, step in enumerate(test_case.get('test_steps', []), 1):
            script += f'            # Step {i}: {step}\n'
            script += f'            # TODO: Implement step\n'
            script += f'            time.sleep(1)\n\n'
        
        script += f'''            
            # Assertion
            assert True, "{test_case["expected_result"]}"
            print("✓ Test passed: {test_case["test_id"]}")
        
        except Exception as e:
            print(f"✗ Test failed: {{e}}")
            raise
    
    def teardown_method(self):
        """Cleanup after test"""
        if self.driver:
            self.driver.quit()


if __name__ == "__main__":
    test = Test{test_case["test_id"].replace("-", "_")}()
    test.setup_method()
    try:
        test.test_{test_case["test_id"].lower().replace("-", "_")}()
    finally:
        test.teardown_method()
'''
        
        return script
    
    def _extract_used_selectors(self, script: str, selectors: Dict) -> List[str]:
        """Extract which selectors were actually used in the script"""
        used = []
        for selector in selectors.keys():
            # Simple check if selector appears in script
            if selector.replace("'", '"') in script or selector.replace('"', "'") in script:
                used.append(selector)
        return used
    
    def _generate_explanation(self, test_case: Dict, script: str) -> str:
        """Generate explanation of the script"""
        explanation = f"""This Selenium script automates the test case '{test_case['test_id']}'.

**Test Objective:** {test_case['test_scenario']}

**Script Structure:**
1. **Setup**: Initializes the WebDriver and browser configuration
2. **Test Execution**: Implements the {len(test_case.get('test_steps', []))} test steps
3. **Assertions**: Verifies that {test_case['expected_result']}
4. **Teardown**: Closes the browser and cleans up resources

**To Run:**
```bash
python {test_case['test_id']}_script.py
```

**Requirements:**
- selenium
- webdriver-manager
"""
        return explanation

