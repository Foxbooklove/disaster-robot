"""
Extended Kalman Filter (EKF)

비선형 시스템에 KF를 적용하는 표준 방법.
시스템 함수를 현재 추정값 주변에서 1차 테일러 전개(선형화)해서 KF 공식 적용.

[KF vs EKF 차이]
KF (선형):
    x_{k+1} = F·x_k + B·u_k                  (선형 행렬)

EKF (비선형):
    x_{k+1} = f(x_k, u_k)                    (일반 함수)
    z_k     = h(x_k)                         (일반 함수)

선형화:
    F_k = ∂f/∂x |_{x̂_{k-1}, u_k}             (Jacobian 행렬)
    H_k = ∂h/∂x |_{x̂_{k|k-1}}

이 F_k, H_k를 KF 공식에 그대로 대입.

[로봇에서 왜 필요한가]
로봇 모션 모델:
    x_{k+1} = x_k + v · cos(ψ_k) · dt        ← cos 비선형
    y_{k+1} = y_k + v · sin(ψ_k) · dt        ← sin 비선형
    ψ_{k+1} = ψ_k + ω · dt                   ← 선형
    
sin/cos 때문에 선형 KF 못 씀 → EKF.

[자코비안 (Jacobian)]
    F = [ ∂x_{k+1}/∂x_k   ∂x_{k+1}/∂y_k   ∂x_{k+1}/∂ψ_k ]
        [ ∂y_{k+1}/∂x_k   ∂y_{k+1}/∂y_k   ∂y_{k+1}/∂ψ_k ]
        [ ∂ψ_{k+1}/∂x_k   ∂ψ_{k+1}/∂y_k   ∂ψ_{k+1}/∂ψ_k ]
    
      = [ 1   0   -v·sin(ψ)·dt ]
        [ 0   1    v·cos(ψ)·dt ]
        [ 0   0          1     ]

[한계]
- 강한 비선형성에선 부정확 (UKF, Particle filter가 대안)
- 자코비안 계산 필요 (해석적/수치적)
- 그러나 실전에선 가장 많이 쓰임 (구현 단순, 빠름)
"""

import math
import numpy as np
from typing import Callable, Optional


class ExtendedKalmanFilter:
    """
    EKF 일반 구현.
    
    f, h, F_jacobian, H_jacobian을 외부에서 주입받음.
    문제 도메인별로 다른 모델 쓸 수 있음.
    """
    
    def __init__(self,
                 f: Callable[[np.ndarray, np.ndarray], np.ndarray],
                 h: Callable[[np.ndarray], np.ndarray],
                 F_jacobian: Callable[[np.ndarray, np.ndarray], np.ndarray],
                 H_jacobian: Callable[[np.ndarray], np.ndarray],
                 Q: np.ndarray, R: np.ndarray,
                 x0: np.ndarray, P0: np.ndarray):
        """
        Args:
            f(x, u) -> x_next: 비선형 상태 전이 함수
            h(x) -> z: 비선형 관측 함수
            F_jacobian(x, u): ∂f/∂x at x
            H_jacobian(x): ∂h/∂x at x
            Q, R, x0, P0: KF와 동일
        """
        self.f = f
        self.h = h
        self.F_jac = F_jacobian
        self.H_jac = H_jacobian
        self.Q = Q
        self.R = R
        self.x = x0.copy()
        self.P = P0.copy()
        self.n = len(x0)
    
    def predict(self, u: np.ndarray) -> np.ndarray:
        # 비선형 함수로 상태 예측
        x_pred = self.f(self.x, u)
        # 자코비안으로 공분산 예측
        F = self.F_jac(self.x, u)
        self.P = F @ self.P @ F.T + self.Q
        self.x = x_pred
        return self.x.copy()
    
    def update(self, z: np.ndarray) -> np.ndarray:
        # 예측된 측정
        z_pred = self.h(self.x)
        # Innovation
        y = z - z_pred
        # 자코비안으로 KF 공식 적용
        H = self.H_jac(self.x)
        S = H @ self.P @ H.T + self.R
        K = self.P @ H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        I = np.eye(self.n)
        self.P = (I - K @ H) @ self.P
        return self.x.copy()


# ════════════════════════════════════════════════════════════════
# 로봇 도메인 특화 EKF
# ════════════════════════════════════════════════════════════════

class RobotPoseEKF:
    """
    Differential drive 로봇용 EKF.
    
    상태 x = [x, y, ψ]ᵀ
    제어 u = [v, ω]ᵀ                    (선속도, 각속도)
    측정 z = [x_meas, y_meas, ψ_meas]ᵀ  (예: GPS+나침반 또는 외부 추적기)
    
    Process model:
        x_{k+1} = x_k + v · cos(ψ_k) · dt
        y_{k+1} = y_k + v · sin(ψ_k) · dt
        ψ_{k+1} = ψ_k + ω · dt
    
    Observation model: 직접 관측
        z = x  (즉 H = I)
    
    실전에선 H가 단위행렬이 아닌 경우가 많음 (예: 거리만 관측하는 비전 마커).
    """
    
    def __init__(self, dt: float,
                 process_noise_std: tuple = (0.05, 0.05, 0.02),
                 measurement_noise_std: tuple = (0.1, 0.1, 0.05),
                 x0: Optional[np.ndarray] = None):
        self.dt = dt
        
        # Process noise (얼마나 모델을 못 믿는지)
        self.Q = np.diag([s**2 for s in process_noise_std])
        # Measurement noise (얼마나 센서를 못 믿는지)
        self.R = np.diag([s**2 for s in measurement_noise_std])
        
        # 초기 상태/공분산
        x0 = x0 if x0 is not None else np.zeros(3)
        P0 = np.eye(3) * 0.01  # 작은 초기 불확실성
        
        self.ekf = ExtendedKalmanFilter(
            f=self._f, h=self._h,
            F_jacobian=self._F_jac, H_jacobian=self._H_jac,
            Q=self.Q, R=self.R, x0=x0, P0=P0,
        )
    
    def _f(self, x: np.ndarray, u: np.ndarray) -> np.ndarray:
        """상태 전이"""
        x_pos, y_pos, psi = x
        v, omega = u
        dt = self.dt
        
        return np.array([
            x_pos + v * math.cos(psi) * dt,
            y_pos + v * math.sin(psi) * dt,
            self._normalize(psi + omega * dt),
        ])
    
    def _F_jac(self, x: np.ndarray, u: np.ndarray) -> np.ndarray:
        """∂f/∂x"""
        psi = x[2]
        v = u[0]
        dt = self.dt
        
        return np.array([
            [1, 0, -v * math.sin(psi) * dt],
            [0, 1,  v * math.cos(psi) * dt],
            [0, 0,  1],
        ])
    
    def _h(self, x: np.ndarray) -> np.ndarray:
        """관측 모델: 직접 관측"""
        return x.copy()
    
    def _H_jac(self, x: np.ndarray) -> np.ndarray:
        return np.eye(3)
    
    def predict(self, v: float, omega: float) -> np.ndarray:
        return self.ekf.predict(np.array([v, omega]))
    
    def update(self, x_meas: float, y_meas: float, psi_meas: float) -> np.ndarray:
        return self.ekf.update(np.array([x_meas, y_meas, psi_meas]))
    
    @property
    def state(self) -> np.ndarray:
        return self.ekf.x.copy()
    
    @property
    def covariance(self) -> np.ndarray:
        return self.ekf.P.copy()
    
    @staticmethod
    def _normalize(angle: float) -> float:
        while angle > math.pi:
            angle -= 2 * math.pi
        while angle < -math.pi:
            angle += 2 * math.pi
        return angle
