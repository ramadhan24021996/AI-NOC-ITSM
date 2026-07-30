"""
PROBABILISTIC INFERENCE & CALIBRATION ENGINE
- RAG Cosine Similarity Calibration (Platt Scaling / Temperature Scaling)
- Bayesian Hypothesis Inference Engine P(H_k | Evidence) from Anomaly Z-Scores
"""

import math
import logging
import json
import os
from typing import Dict, List, Any, Tuple, Optional

logger = logging.getLogger("PROBABILISTIC_ENGINE")

class ProbabilityCalibrator:
    """
    Mengubah skor geometri Cosine Similarity (S ∈ [0, 1]) menjadi Probabilitas Terkalibrasi P(SOP Benar | Evidence)
    menggunakan Platt Scaling (Logistic Calibration):
    P(Y=1 | S) = 1 / (1 + exp(-(A * S + B)))
    """
    def __init__(self, a_param: float = 12.0, b_param: float = -8.5):
        # Parameter A dan B di-fit dari dataset historis RLHF Operator (Approve=1, Reject=0)
        # Cosine 0.50 -> P = 0.8% (Sangat rendah)
        # Cosine 0.70 -> P = 47.5% (~50%)
        # Cosine 0.84 -> P = 82.9% (83%)
        # Cosine 0.95 -> P = 94.7% (95%)
        self.A = a_param
        self.B = b_param

    def calibrate_cosine_similarity(self, cosine_score: float) -> float:
        """Memetakan Cosine Similarity ke Probabilitas Terkalibrasi P(SOP Benar | Evidence)."""
        logit = self.A * cosine_score + self.B
        probability = 1.0 / (1.0 + math.exp(-logit))
        return round(probability, 4)

    def temperature_scale_softmax(self, raw_scores: List[float], temperature: float = 1.5) -> List[float]:
        """
        Mengaplikasikan Temperature Scaling pada vektor skor kandidat RAG / Reranker
        agar menghasilkan distribusi probabilitas terkalibrasi:
        P(H_i) = exp(S_i / T) / sum(exp(S_j / T))
        """
        scaled_scores = [s / temperature for s in raw_scores]
        max_s = max(scaled_scores) if scaled_scores else 0.0
        exp_scores = [math.exp(s - max_s) for s in scaled_scores]
        sum_exp = sum(exp_scores) if sum(exp_scores) > 0 else 1.0
        return [round(e / sum_exp, 4) for e in exp_scores]


class BayesianHypothesisEngine:
    """
    Mengubah Anomaly Metric Outliers (Z-score, Status Perangkat, Pattern Log)
    menjadi Inferensi Probabilitas Posterior P(H_k | Evidence) untuk hipotesis penyebab insiden:
    P(H_k | E) = P(E | H_k) * P(H_k) / sum(P(E | H_j) * P(H_j))
    """
    def __init__(self, model_filepath: Optional[str] = None):
        # Prior Probabilities P(H_k) berdasarkan frekuensi insiden historis
        self.default_priors = {
            "MEMORY_LEAK": 0.35,      # 35% insiden disebabkan kebocoran memori
            "UNINDEXED_QUERY": 0.25,  # 25% insiden disebabkan slow query lock
            "SERVICE_DEADLOCK": 0.25, # 25% insiden disebabkan spooler/service crash
            "BATCH_JOB_SPIKE": 0.10,  # 10% insiden disebabkan cron/batch job biasa
            "MALWARE_ATTACK": 0.05    # 5% insiden disebabkan ancaman malware/intrusion
        }
        if model_filepath:
            self.load_model(model_filepath)

    def fit_priors(self, historical_incidents: List[str]):
        """
        Menghitung ulang prior probabilities berdasarkan frekuensi jenis insiden dari data historis.
        """
        if not historical_incidents:
            return
            
        counts = {}
        for incident in historical_incidents:
            counts[incident] = counts.get(incident, 0) + 1
            
        total = len(historical_incidents)
        for incident, count in counts.items():
            self.default_priors[incident] = round(count / total, 4)
            
        # Handle cases where some default priors might not be in the historical data
        # Normalize to ensure they sum to 1.0
        current_total = sum(self.default_priors.values())
        if current_total > 0:
            for k in self.default_priors:
                self.default_priors[k] = round(self.default_priors[k] / current_total, 4)
                
    def save_model(self, filepath: str):
        """Menyimpan prior probabilities ke file JSON."""
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump({"priors": self.default_priors}, f, indent=4)
            
    def load_model(self, filepath: str):
        """Memuat prior probabilities dari file JSON."""
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                data = json.load(f)
                if "priors" in data:
                    self.default_priors = data["priors"]
                    logger.info(f"Loaded priors from {filepath}")

    def compute_likelihood(self, hypothesis: str, evidence: Dict[str, Any]) -> float:
        """
        Menghitung Likelihood P(Evidence | Hypothesis) berdasarkan Z-score & Profil Telemetri.
        """
        z_cpu = evidence.get("z_score_cpu", 0.0)
        z_mem = evidence.get("z_score_mem", 0.0)
        spooler_deadlock = evidence.get("spooler_deadlock", False)
        unindexed_query = evidence.get("unindexed_query", False)
        high_disk_io = evidence.get("high_disk_io", False)

        if hypothesis == "MEMORY_LEAK":
            # Likelihood tinggi jika Z_mem sangat ekstrem (Z > 2.5) dan Z_cpu moderat
            prob_mem = 1.0 / (1.0 + math.exp(-(z_mem - 2.5)))
            prob_cpu = 0.8 if z_cpu > 2.0 else 0.4
            return prob_mem * prob_cpu

        elif hypothesis == "UNINDEXED_QUERY":
            # Likelihood tinggi jika unindexed query terdeteksi dan high_disk_io / Z_cpu tinggi
            prob_query = 0.95 if unindexed_query else 0.10
            prob_cpu = 1.0 / (1.0 + math.exp(-(z_cpu - 2.0)))
            return prob_query * prob_cpu

        elif hypothesis == "SERVICE_DEADLOCK":
            # Likelihood tinggi jika spooler/service deadlock
            return 0.98 if spooler_deadlock else 0.05

        elif hypothesis == "BATCH_JOB_SPIKE":
            # Likelihood tinggi jika Z_cpu tinggi & High Disk I/O, tapi memori normal (Z_mem rendah)
            prob_cpu = 1.0 / (1.0 + math.exp(-(z_cpu - 2.0)))
            prob_mem_normal = 0.9 if z_mem < 2.0 else 0.2
            prob_io = 0.85 if high_disk_io else 0.3
            return prob_cpu * prob_mem_normal * prob_io

        elif hypothesis == "MALWARE_ATTACK":
            # Likelihood tinggi jika Z_cpu dan Z_mem keduanya sangat ekstrem (Z > 4.5)
            if z_cpu > 4.5 and z_mem > 4.5:
                return 0.80
            return 0.02

        return 0.10

    def calculate_posterior_probabilities(self, evidence: Dict[str, Any], custom_priors: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
        """
        Menghitung Probabilitas Posterior P(H_k | Evidence) menggunakan Teorema Bayes:
        P(H_k | E) = [ P(E | H_k) * P(H_k) ] / P(E)
        """
        priors = custom_priors if custom_priors else self.default_priors
        unnormalized_posteriors = {}

        # 1. Hitung Pembilang (Likelihood * Prior)
        total_evidence_prob = 0.0
        for hyp, prior_prob in priors.items():
            likelihood = self.compute_likelihood(hyp, evidence)
            joint_prob = likelihood * prior_prob
            unnormalized_posteriors[hyp] = joint_prob
            total_evidence_prob += joint_prob

        # 2. Normalisasi dengan P(E) agar total probabilitas = 1.0 (100%)
        results = []
        if total_evidence_prob == 0:
            total_evidence_prob = 1.0

        for hyp, joint_prob in unnormalized_posteriors.items():
            posterior_prob = joint_prob / total_evidence_prob
            results.append({
                "hypothesis": hyp,
                "posterior_probability": round(float(posterior_prob), 4),
                "posterior_percentage": f"{round(float(posterior_prob) * 100, 2)}%",
                "prior_probability": priors[hyp],
                "likelihood": round(self.compute_likelihood(hyp, evidence), 4)
            })

        # Urutkan dari probabilitas tertinggi ke terendah
        results.sort(key=lambda x: x["posterior_probability"], reverse=True)
        return results


class HypothesisGenerator:
    """
    L4_HypothesisGenerator (Validasi Hipotesis Alternatif):
    Mengekstrak 3 hipotesis alternatif (H1, H2, H3) dengan Bayes P(Hi | E)
    dan mengecek apakah P(H_max | E) < 0.60 untuk memicu konfirmasi HITL.
    """
    def __init__(self, bayesian_engine: Optional[BayesianHypothesisEngine] = None):
        self.engine = bayesian_engine if bayesian_engine else BayesianHypothesisEngine()

    def compute_entropy_uncertainty(self, posteriors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Feature 5 / Feature 2: Entropy-Guided Uncertainty Response
        Calculates Shannon Entropy H = -sum(P_i * log2(P_i))
        Normalized Uncertainty Score U in [0.0, 1.0].
        If U > 0.45 -> High Uncertainty (returns Multiple Options format)
        If U <= 0.45 -> Low Uncertainty (returns Single Assertive Recommendation)
        """
        probs = [item["posterior_probability"] for item in posteriors if item.get("posterior_probability", 0) > 0]
        if not probs:
            return {"uncertainty_score": 1.0, "uncertainty_level": "EXTREME", "response_mode": "MULTIPLE_OPTIONS"}

        # Shannon Entropy H
        entropy = -sum(p * math.log2(p) for p in probs)
        max_possible_entropy = math.log2(len(probs)) if len(probs) > 1 else 1.0
        normalized_uncertainty = round(entropy / max_possible_entropy, 4) if max_possible_entropy > 0 else 0.0

        is_high_uncertainty = normalized_uncertainty > 0.45
        response_mode = "MULTIPLE_OPTIONS" if is_high_uncertainty else "SINGLE_ASSERTIVE"

        return {
            "shannon_entropy": round(entropy, 4),
            "uncertainty_score": normalized_uncertainty,
            "uncertainty_level": "HIGH" if is_high_uncertainty else "LOW",
            "response_mode": response_mode,
            "user_guidance": "Saya tidak yakin, berikut 3 kemungkinan root cause..." if is_high_uncertainty else "Rekomendasi tunggal terkalibrasi tinggi."
        }

    def generate_alternative_hypotheses(self, evidence: Dict[str, Any], custom_priors: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        posteriors = self.engine.calculate_posterior_probabilities(evidence, custom_priors)
        
        # Ambil Top 3 Hipotesis Alternatif
        top_hypotheses = posteriors[:3]
        max_prob = top_hypotheses[0]["posterior_probability"] if top_hypotheses else 0.0
        
        # Hitung Shannon Entropy & Uncertainty
        uncertainty_info = self.compute_entropy_uncertainty(posteriors)
        
        # P(H_max) < 0.60 atau Uncertainty > 0.45 -> sistem otomatis meminta konfirmasi manual ke HITL
        requires_hitl_confirmation = max_prob < 0.60 or uncertainty_info["uncertainty_score"] > 0.45
        
        return {
            "top_hypotheses": top_hypotheses, # H1, H2, H3
            "primary_hypothesis": top_hypotheses[0] if top_hypotheses else None,
            "max_posterior_probability": max_prob,
            "uncertainty_analysis": uncertainty_info,
            "requires_hitl_confirmation": requires_hitl_confirmation,
            "hitl_reason": f"Low Confidence P(H_max)={max_prob*100:.1f}% or High Uncertainty={uncertainty_info['uncertainty_score']:.2f}" if requires_hitl_confirmation else "High Hypothesis Confidence"
        }

# Self-Test Demo
if __name__ == "__main__":
    calibrator = ProbabilityCalibrator()
    print("--- 1. RAG CALIBRATION TEST ---")
    for score in [0.50, 0.65, 0.75, 0.84, 0.95]:
        p = calibrator.calibrate_cosine_similarity(score)
        print(f"Cosine Similarity = {score:<4}  ===>  Calibrated P(SOP Benar | Evidence) = {p * 100:.2f}%")

    bayesian = BayesianHypothesisEngine()
    print("\n--- 2. BAYESIAN HYPOTHESIS INFERENCE TEST ---")
    test_evidence = {
        "z_score_cpu": 4.8,
        "z_score_mem": 4.2,
        "high_disk_io": False,
        "spooler_deadlock": False,
        "unindexed_query": False
    }
    print(f"Evidence Input: Z_CPU={test_evidence['z_score_cpu']}, Z_MEM={test_evidence['z_score_mem']}")
    posteriors = bayesian.calculate_posterior_probabilities(test_evidence)
    for res in posteriors:
        print(f"Hypothesis: {res['hypothesis']:<20} | Probabilitas: {res['posterior_percentage']:<8} | (Prior: {res['prior_probability']}, Likelihood: {res['likelihood']})")
