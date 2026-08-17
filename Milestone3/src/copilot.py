import json
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

class AICopilot:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.gpu_available = torch.cuda.is_available()
        
    def load_model(self) -> bool:
        """Loads Qwen2.5-3B-Instruct in 4-bit quantization if GPU is available."""
        model_id = "Qwen/Qwen2.5-3B-Instruct"
        print(f"[AICopilot] GPU Availability: {self.gpu_available}")
        
        if not self.gpu_available:
            print("[AICopilot] GPU not found. Falling back to high-fidelity rule-based recommendation generator.")
            return False
            
        try:
            print(f"[AICopilot] Attempting to load {model_id} in 4-bit NF4...")
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16
            )
            
            # Using low CPU memory load as well
            self.tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
            self.model = AutoModelForCausalLM.from_pretrained(
                model_id,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True
            )
            print("[AICopilot] GPU 4-bit NF4 load succeeded.")
            return True
        except Exception as e:
            print(f"[AICopilot] GPU load failed: {e}. Falling back to rule-based generator.")
            self.model = None
            self.tokenizer = None
            return False

    def generate_recommendation(self, distance: float, weight: float, traffic: float, weather: float, safety_score: float) -> str:
        """Generates shipping/routing carrier recommendations in JSON format."""
        
        prompt_text = f"""
        Analyze logistics metrics and generate a route carrier selection recommendation.
        
        Input Details:
        - Transit Distance: {distance:.1f} miles
        - Cargo Weight: {weight:.1f} lbs
        - Traffic Congestion Level: {traffic:.2f} (0=empty, 1=blocked)
        - Extreme Weather Index: {weather:.2f} (0=clear, 1=severe storm)
        - Carrier Safety Score: {safety_score:.1f} (out of 100)
        
        Generate a structured JSON output with the exact keys:
        - "price_status": "Fair" / "High" / "Low"
        - "delay_risk": "Low" / "Medium" / "High"
        - "compliance_risk": "Low" / "Medium" / "High"
        - "recommendation_text": "A descriptive, professional 1-2 sentence assessment."
        """
        
        if self.model is not None and self.tokenizer is not None:
            try:
                messages = [
                    {"role": "system", "content": "You are FreightQuote AI Copilot. Return ONLY a single JSON block."},
                    {"role": "user", "content": prompt_text}
                ]
                # Format using chat template
                text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                model_inputs = self.tokenizer([text], return_tensors="pt").to("cuda")
                
                with torch.no_grad():
                    generated_ids = self.model.generate(
                        **model_inputs,
                        max_new_tokens=256,
                        temperature=0.6,
                        do_sample=True
                    )
                
                # Slicing input prompt
                generated_ids = [
                    output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
                ]
                response_text = self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
                
                # Check if output is valid JSON
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                if json_start != -1 and json_end != -1:
                    json_str = response_text[json_start:json_end]
                    json.loads(json_str) # test validation
                    return json_str
            except Exception as e:
                print(f"[AICopilot] Inference error: {e}. Executing fallback recommendation engine.")
                
        # High fidelity fallback rules (mimicking LLM output structure)
        # Determine risks
        if distance > 1500 or traffic > 0.7 or weather > 0.7:
            delay_risk = "High"
        elif distance > 700 or traffic > 0.4 or weather > 0.4:
            delay_risk = "Medium"
        else:
            delay_risk = "Low"
            
        if safety_score < 70:
            compliance_risk = "High"
        elif safety_score < 85:
            compliance_risk = "Medium"
        else:
            compliance_risk = "Low"
            
        est_price = (distance * 1.5) + (weight * 0.05)
        price_status = "High" if est_price > 3000 else ("Fair" if est_price > 1000 else "Low")
        
        rec_text = (
            f"The shipment spanning {distance:.0f} miles is approved with {delay_risk} transit risk and {compliance_risk} carrier safety compliance. "
            f"Carrier is selected based on a safety profile of {safety_score:.0f}/100."
        )
        
        res = {
            "price_status": price_status,
            "delay_risk": delay_risk,
            "compliance_risk": compliance_risk,
            "recommendation_text": rec_text
        }
        return json.dumps(res, indent=4)
