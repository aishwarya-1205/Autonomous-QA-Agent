import pymupdf  # PyMuPDF
from pathlib import Path
from typing import Dict, Any
import json
import markdown
from bs4 import BeautifulSoup


class DocumentParser:
    def parse_file(self, file_path: Path) -> Dict[str, Any]:
        """Parse a file based on its extension"""
        extension = file_path.suffix.lower()
        
        parsers = {
            '.pdf': self._parse_pdf,
            '.md': self._parse_markdown,
            '.txt': self._parse_text,
            '.json': self._parse_json,
        }
        
        parser = parsers.get(extension)
        if not parser:
            raise ValueError(f"Unsupported file type: {extension}")
        
        content = parser(file_path)
        
        return {
            'content': content,
            'source': file_path.name,
            'type': extension[1:],  # Remove dot
            'path': str(file_path)
        }
    
    def _parse_pdf(self, file_path: Path) -> str:
        """Parse PDF file"""
        doc = pymupdf.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    
    def _parse_markdown(self, file_path: Path) -> str:
        """Parse Markdown file"""
        content = file_path.read_text(encoding='utf-8')
        # Convert to plain text (remove markdown syntax)
        html = markdown.markdown(content)
        soup = BeautifulSoup(html, 'html.parser')
        return soup.get_text()
    
    def _parse_text(self, file_path: Path) -> str:
        """Parse text file"""
        return file_path.read_text(encoding='utf-8')
    
    def _parse_json(self, file_path: Path) -> str:
        """Parse JSON file"""
        data = json.loads(file_path.read_text(encoding='utf-8'))
        return json.dumps(data, indent=2)
    
    def parse_html(self, html_content: str) -> Dict[str, Any]:
        """Parse HTML content and extract structure"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        elements = []
        forms = []
        
        # Extract interactive elements
        for tag in ['input', 'button', 'select', 'textarea']:
            for element in soup.find_all(tag):
                elements.append({
                    'tag': tag,
                    'id': element.get('id'),
                    'name': element.get('name'),
                    'type': element.get('type'),
                    'class': element.get('class')
                })
        
        # Extract forms
        for form in soup.find_all('form'):
            forms.append({
                'id': form.get('id'),
                'action': form.get('action'),
                'method': form.get('method')
            })
        
        return {
            'elements': elements,
            'forms': forms,
            'title': soup.title.string if soup.title else None
        }
    
    def parse_html_file(self, html_content: str, source: str) -> Dict[str, Any]:
        """Parse HTML file for knowledge base"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract text content
        text_content = soup.get_text(separator='\n', strip=True)
        
        # Add structure information
        structure_info = self.parse_html(html_content)
        
        # Combine into searchable content
        content = f"HTML Structure:\n{text_content}\n\n"
        content += f"Interactive Elements: {len(structure_info['elements'])}\n"
        content += f"Forms: {len(structure_info['forms'])}\n"
        
        return {
            'content': content,
            'source': source,
            'type': 'html',
            'metadata': structure_info
        }