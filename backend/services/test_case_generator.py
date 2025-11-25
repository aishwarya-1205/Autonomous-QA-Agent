"""
Test Case Generator Service
Generates comprehensive test cases using RAG and LLM
"""

import json
import re
from typing import List, Dict
from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()


class TestCaseGenerator:
    def __init__(self, rag_service):
        self.rag_service = rag_service
        self.client = Groq(api_key=os.getenv('GROQ_API_KEY'))
        self.model = os.getenv('LLM_MODEL', 'mixtral-8x7b-32768')
        
    def generate_test_cases(self, query: str, num_cases: int = 10) -> List[Dict]:
        """Generate test cases based on query using RAG"""
        
        # Retrieve relevant context from vector DB
        context_docs = self.rag_service.retrieve_context(query, k=5)
        
        # Build context string with source attribution
        context_str = self._build_context_string(context_docs)
        
        # Generate test cases using LLM
        test_cases = self._generate_with_llm(query, context_str, num_cases)
        
        return test_cases
    
    def _build_context_string(self, context_docs: List[Dict]) -> str:
        """Build formatted context string from retrieved documents"""
        context_parts = []
        
        for i, doc in enumerate(context_docs, 1):
            source = doc.get('metadata', {}).get('source', 'unknown')
            content = doc.get('content', '')
            context_parts.append(f"[Document {i} - {source}]\n{content}\n")
        
        return "\n".join(context_parts)
    
    def _generate_with_llm(self, query: str, context: str, num_cases: int) -> List[Dict]:
        """Generate test cases using LLM with RAG context"""
        
        system_prompt = """You are an expert QA engineer and test architect. Your task is to generate comprehensive, professional test cases based on the provided documentation.

CRITICAL REQUIREMENTS:
1. Generate test cases in VALID JSON format (must be parseable)
2. Every test case MUST reference specific source documents
3. NO hallucinations - only use information from provided documents
4. Include positive, negative, and edge test cases
5. Be specific and actionable

Each test case must have this structure:
{
    "test_id": "TC-XXX",
    "feature": "Feature name",
    "test_scenario": "Clear description",
    "test_type": "positive|negative|edge",
    "preconditions": "Setup needed",
    "test_steps": ["Step 1", "Step 2", ...],
    "expected_result": "What should happen",
    "grounded_in": ["source_file.md", ...],
    "priority": "high|medium|low"
}

Return ONLY a JSON array of test cases, no additional text."""

        user_prompt = f"""Based on the following documentation, generate {num_cases} comprehensive test cases for: {query}

DOCUMENTATION:
{context}

Generate diverse test cases covering:
- Positive scenarios (happy path)
- Negative scenarios (invalid inputs, errors)
- Edge cases (boundaries, limits)

Return ONLY valid JSON array, no markdown formatting."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=4096
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Clean up response (remove markdown code blocks if present)
            response_text = re.sub(r'```json\s*', '', response_text)
            response_text = re.sub(r'```\s*$', '', response_text)
            response_text = response_text.strip()
            
            # Parse JSON
            try:
                test_cases = json.loads(response_text)
                
                # Validate and ensure it's a list
                if not isinstance(test_cases, list):
                    test_cases = [test_cases]
                
                # Validate each test case has required fields
                validated_cases = []
                for i, tc in enumerate(test_cases[:num_cases], 1):
                    validated_tc = self._validate_test_case(tc, i)
                    validated_cases.append(validated_tc)
                
                return validated_cases
            
            except json.JSONDecodeError as e:
                print(f"JSON Parse Error: {e}")
                print(f"Response: {response_text[:500]}")
                
                # Fallback: create basic test cases
                return self._create_fallback_test_cases(query, context, num_cases)
        
        except Exception as e:
            print(f"LLM Error: {e}")
            return self._create_fallback_test_cases(query, context, num_cases)
    
    def _validate_test_case(self, tc: Dict, index: int) -> Dict:
        """Validate and normalize test case structure"""
        return {
            "test_id": tc.get("test_id", f"TC-{index:03d}"),
            "feature": tc.get("feature", "Unknown Feature"),
            "test_scenario": tc.get("test_scenario", "Test scenario"),
            "test_type": tc.get("test_type", "positive"),
            "preconditions": tc.get("preconditions", "None"),
            "test_steps": tc.get("test_steps", ["Execute test"]) if isinstance(tc.get("test_steps"), list) else ["Execute test"],
            "expected_result": tc.get("expected_result", "Test passes"),
            "grounded_in": tc.get("grounded_in", ["documentation"]) if isinstance(tc.get("grounded_in"), list) else ["documentation"],
            "priority": tc.get("priority", "medium")
        }
    
    def _create_fallback_test_cases(self, query: str, context: str, num_cases: int) -> List[Dict]:
        """Create basic test cases if LLM fails"""
        
        # Extract features from context
        features = self._extract_features_from_context(context)
        
        test_cases = []
        for i in range(min(num_cases, len(features) or 3)):
            feature = features[i] if i < len(features) else "General Functionality"
            
            test_cases.append({
                "test_id": f"TC-{i+1:03d}",
                "feature": feature,
                "test_scenario": f"Test {feature} functionality",
                "test_type": "positive" if i % 3 != 1 else "negative",
                "preconditions": "Application is loaded",
                "test_steps": [
                    "Navigate to the feature",
                    "Perform action",
                    "Verify result"
                ],
                "expected_result": "Feature works as expected",
                "grounded_in": ["documentation"],
                "priority": "medium"
            })
        
        return test_cases
    
    def _extract_features_from_context(self, context: str) -> List[str]:
        """Extract potential features from context"""
        # Simple extraction based on common patterns
        features = []
        
        # Look for common feature keywords
        keywords = ['button', 'form', 'input', 'field', 'cart', 'checkout', 'payment', 'discount', 'shipping']
        
        for keyword in keywords:
            if keyword.lower() in context.lower():
                features.append(keyword.capitalize())
        
        return list(set(features))[:10]  