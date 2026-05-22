---
topics: ["公式生成", "研究方法", "数学建模"]
tags: ["formula", "latex", "method", "quantitative"]
priority: high
---

# 研究方法公式生成技能

为工程管理硕士论文中涉及的研究方法生成正确的 LaTeX 数学公式。
每个方法包含：核心公式、变量定义、使用场景、常见错误。

## 公式通用规范

- 所有公式使用 LaTeX 语法：`$...$`（行内）、`$$...$$`（行间）、`\begin{equation}...\end{equation}`（编号）
- 变量用斜体，运算符用正体：`$x_i$` vs `\max`、`\sum`
- 中文文档中公式编号格式：`(3-1)`、`(4-5)` 表示章-序号
- 矩阵用 `\begin{bmatrix} ... \end{bmatrix}`
- 上下标：`x_{ij}` 不是 `x_ij`
- 分数：`\frac{a}{b}`
- 公式后必跟变量说明："式中：$x_{ij}$ 表示..."

---

## 1. 层次分析法 (AHP)

### 1.1 判断矩阵

$$A = \begin{bmatrix}
a_{11} & a_{12} & \cdots & a_{1n} \\
a_{21} & a_{22} & \cdots & a_{2n} \\
\vdots & \vdots & \ddots & \vdots \\
a_{n1} & a_{n2} & \cdots & a_{nn}
\end{bmatrix}$$

式中：$a_{ij}$ 表示指标 $i$ 相对于指标 $j$ 的重要程度，采用 1-9 标度法，满足 $a_{ij} = 1/a_{ji}$，$a_{ii} = 1$。

### 1.2 方根法求权重

$$w_i = \frac{\left(\prod_{j=1}^{n} a_{ij}\right)^{1/n}}{\sum_{k=1}^{n} \left(\prod_{j=1}^{n} a_{kj}\right)^{1/n}}$$

式中：$w_i$ 为第 $i$ 个指标的权重，$n$ 为指标数量。

### 1.3 最大特征值

$$\lambda_{\max} = \frac{1}{n} \sum_{i=1}^{n} \frac{(A w)_i}{w_i}$$

式中：$(Aw)_i$ 为判断矩阵 $A$ 与权重向量 $w$ 乘积的第 $i$ 个分量。

### 1.4 一致性检验

$$CI = \frac{\lambda_{\max} - n}{n - 1}$$

$$CR = \frac{CI}{RI}$$

式中：$CR < 0.1$ 时通过一致性检验。$RI$ 为随机一致性指标，查表获取（$n=3$ 时 $RI=0.58$，$n=4$ 时 $RI=0.90$，$n=5$ 时 $RI=1.12$）。

**常见错误**：忘记报告 CR 值；RI 值查错；判断矩阵不对称。

---

## 2. 模糊综合评价法 (FCE)

### 2.1 隶属度矩阵

$$R = \begin{bmatrix}
r_{11} & r_{12} & \cdots & r_{1m} \\
r_{21} & r_{22} & \cdots & r_{2m} \\
\vdots & \vdots & \ddots & \vdots \\
r_{n1} & r_{n2} & \cdots & r_{nm}
\end{bmatrix}$$

式中：$r_{ij}$ 表示第 $i$ 个指标对第 $j$ 个评语等级的隶属度，$0 \leq r_{ij} \leq 1$，$\sum_{j=1}^{m} r_{ij} = 1$。

### 2.2 模糊合成

$$B = W \circ R = (b_1, b_2, \ldots, b_m)$$

$$b_j = \sum_{i=1}^{n} w_i \cdot r_{ij}$$

式中：$W$ 为权重向量，$\circ$ 为模糊合成算子（常用加权平均算子），$B$ 为综合评价向量。

### 2.3 综合得分

$$S = B \cdot V^T = \sum_{j=1}^{m} b_j \cdot v_j$$

式中：$V = (v_1, v_2, \ldots, v_m)$ 为评语等级对应的分值向量，如 $V = (90, 70, 50, 30, 10)$ 对应五级评语（很好、较好、一般、较差、很差）。

**常见错误**：多级评价时只做一级合成；隶属度不归一化；评语分值间距不合理。

---

## 3. 熵权法 (Entropy Weight)

### 3.1 数据标准化

正向指标（越大越好）：

$$x'_{ij} = \frac{x_{ij} - \min(x_j)}{\max(x_j) - \min(x_j)}$$

负向指标（越小越好）：

$$x'_{ij} = \frac{\max(x_j) - x_{ij}}{\max(x_j) - \min(x_j)}$$

### 3.2 比重矩阵

$$p_{ij} = \frac{x'_{ij}}{\sum_{i=1}^{m} x'_{ij}}$$

### 3.3 信息熵

$$e_j = -\frac{1}{\ln m} \sum_{i=1}^{m} p_{ij} \ln(p_{ij})$$

式中：当 $p_{ij} = 0$ 时，令 $p_{ij} \ln(p_{ij}) = 0$。

### 3.4 权重计算

$$w_j = \frac{1 - e_j}{\sum_{k=1}^{n} (1 - e_k)}$$

式中：$1 - e_j$ 为第 $j$ 个指标的差异系数。

**常见错误**：忘记处理 $p_{ij}=0$ 的情况；标准化方向弄反（正向/负向）。

---

## 4. TOPSIS 法

### 4.1 加权标准化矩阵

$$v_{ij} = w_j \cdot x'_{ij}$$

### 4.2 正负理想解

$$A^+ = \{\max_i v_{i1}, \max_i v_{i2}, \ldots, \max_i v_{in}\}$$

$$A^- = \{\min_i v_{i1}, \min_i v_{i2}, \ldots, \min_i v_{in}\}$$

### 4.3 距离计算

$$D_i^+ = \sqrt{\sum_{j=1}^{n} (v_{ij} - v_j^+)^2}$$

$$D_i^- = \sqrt{\sum_{j=1}^{n} (v_{ij} - v_j^-)^2}$$

### 4.4 相对贴近度

$$C_i = \frac{D_i^-}{D_i^+ + D_i^-}$$

式中：$C_i \in [0, 1]$，值越大方案越优。

**常见错误**：权重未归一化；正负理想解取错方向（部分指标为负向指标）。

---

## 5. 灰色关联分析 (GRA)

### 5.1 无量纲化（初值化）

$$x'_i(k) = \frac{x_i(k)}{x_0(k)}$$

### 5.2 关联系数

$$\xi_i(k) = \frac{\min_i \min_k |x_0(k) - x_i(k)| + \rho \cdot \max_i \max_k |x_0(k) - x_i(k)|}{|x_0(k) - x_i(k)| + \rho \cdot \max_i \max_k |x_0(k) - x_i(k)|}$$

式中：$\rho$ 为分辨系数，通常取 $\rho = 0.5$。

### 5.3 关联度

$$r_i = \frac{1}{n} \sum_{k=1}^{n} \xi_i(k)$$

**常见错误**：$\rho$ 取值不说明理由；未做无量纲化直接计算。

---

## 6. 数据包络分析 (DEA - CCR 模型)

### 6.1 CCR 模型（投入导向）

$$\begin{aligned}
\min & \quad \theta \\
\text{s.t.} & \quad \sum_{j=1}^{n} \lambda_j x_{ij} \leq \theta x_{i0}, \quad i = 1,2,\ldots,m \\
& \quad \sum_{j=1}^{n} \lambda_j y_{rj} \geq y_{r0}, \quad r = 1,2,\ldots,s \\
& \quad \lambda_j \geq 0, \quad j = 1,2,\ldots,n
\end{aligned}$$

式中：$\theta$ 为效率值（$\theta \leq 1$，$\theta = 1$ 表示 DEA 有效），$\lambda_j$ 为权重变量，$x_{ij}$ 为第 $j$ 个 DMU 的第 $i$ 项投入，$y_{rj}$ 为第 $j$ 个 DMU 的第 $r$ 项产出。

**常见错误**：DMU 数量不足（应 $\geq 2(m+s)$）；投入产出指标存在强线性相关。

---

## 7. 回归分析

### 7.1 多元线性回归

$$Y = \beta_0 + \beta_1 X_1 + \beta_2 X_2 + \cdots + \beta_k X_k + \varepsilon$$

式中：$\beta_0$ 为截距，$\beta_i$ 为偏回归系数，$\varepsilon \sim N(0, \sigma^2)$ 为随机误差。

### 7.2 最小二乘估计

$$\hat{\beta} = (X^T X)^{-1} X^T Y$$

### 7.3 拟合优度

$$R^2 = 1 - \frac{SS_{\text{res}}}{SS_{\text{tot}}} = 1 - \frac{\sum (y_i - \hat{y}_i)^2}{\sum (y_i - \bar{y})^2}$$

调整 $R^2$：

$$R^2_{\text{adj}} = 1 - \frac{(1 - R^2)(n - 1)}{n - k - 1}$$

### 7.4 F 检验

$$F = \frac{SS_{\text{reg}} / k}{SS_{\text{res}} / (n - k - 1)} = \frac{R^2 / k}{(1 - R^2) / (n - k - 1)}$$

### 7.5 t 检验（单系数）

$$t_i = \frac{\hat{\beta}_i}{\text{SE}(\hat{\beta}_i)}$$

**常见错误**：未报告 $p$ 值和置信区间；未检验多重共线性（VIF > 10 表示严重）；未检验异方差。

---

## 8. 主成分分析 (PCA)

### 8.1 协方差矩阵（或相关系数矩阵）

$$R = \frac{1}{n-1} X^{*T} X^*$$

式中：$X^*$ 为标准化后的数据矩阵。

### 8.2 特征方程

$$R \cdot v_i = \lambda_i \cdot v_i$$

式中：$\lambda_i$ 为第 $i$ 个特征值（从大到小排列），$v_i$ 为对应特征向量。

### 8.3 方差贡献率

$$\alpha_k = \frac{\lambda_k}{\sum_{i=1}^{p} \lambda_i}$$

累积贡献率：

$$\beta_k = \frac{\sum_{i=1}^{k} \lambda_i}{\sum_{i=1}^{p} \lambda_i}$$

（通常取 $\beta_k \geq 85\%$ 的前 $k$ 个主成分）

### 8.4 主成分得分

$$F_i = v_{i1} X_1^* + v_{i2} X_2^* + \cdots + v_{ip} X_p^*$$

综合得分（加权）：

$$F = \sum_{i=1}^{k} \alpha_i F_i$$

**常见错误**：未做 KMO 和 Bartlett 检验（KMO < 0.6 不适合做主成分）；直接用协方差矩阵而非相关系数矩阵。

---

## 9. 因子分析

### 9.1 因子模型

$$X_i = a_{i1} F_1 + a_{i2} F_2 + \cdots + a_{im} F_m + \varepsilon_i$$

式中：$F_j$ 为公共因子，$a_{ij}$ 为因子载荷，$\varepsilon_i$ 为特殊因子。

矩阵形式：

$$X = A F + \varepsilon$$

### 9.2 方差贡献

$$g_j^2 = \sum_{i=1}^{p} a_{ij}^2$$

式中：$g_j^2$ 为第 $j$ 个公因子对全部原始变量的方差贡献。

### 9.3 共性方差

$$h_i^2 = \sum_{j=1}^{m} a_{ij}^2$$

**常见错误**：因子载荷 < 0.5 的变量未处理；未报告旋转方法（通常用最大方差旋转 Varimax）。

---

## 10. 结构方程模型 (SEM)

### 10.1 测量模型

$$X = \Lambda_X \xi + \delta$$

$$Y = \Lambda_Y \eta + \varepsilon$$

式中：$\xi$ 为外生潜变量，$\eta$ 为内生潜变量，$\Lambda$ 为因子载荷矩阵，$\delta$、$\varepsilon$ 为测量误差。

### 10.2 结构模型

$$\eta = B \eta + \Gamma \xi + \zeta$$

式中：$B$ 为内生潜变量间的关系矩阵，$\Gamma$ 为外生潜变量对内生潜变量的影响矩阵，$\zeta$ 为结构残差。

### 10.3 拟合指标（必须报告）

- $\chi^2/df < 3$（卡方自由度比）
- $GFI > 0.9$（拟合优度指数）
- $RMSEA < 0.08$（近似误差均方根）
- $CFI > 0.9$（比较拟合指数）
- $TLI > 0.9$（Tucker-Lewis 指数）
- $SRMR < 0.05$（标准化残差均方根）

**常见错误**：只报告部分拟合指标；样本量不足（至少 200）；未报告组合信度 CR 和平均方差提取量 AVE。

---

## 11. FMEA（失效模式与影响分析）

### 11.1 风险优先数

$$RPN = S \times O \times D$$

式中：$S$ 为严重度（Severity），$O$ 为发生频度（Occurrence），$D$ 为检测难度（Detection），均采用 1-10 评分。

### 11.2 改进效果

$$\Delta RPN = RPN_{\text{before}} - RPN_{\text{after}}$$

**常见错误**：S/O/D 评分标准未定义；只报告 RPN 不报告单项得分。

---

## 12. 挣值管理 (EVM)

### 12.1 基本指标

$$CV = EV - AC \quad \text{（成本偏差）}$$

$$SV = EV - PV \quad \text{（进度偏差）}$$

$$CPI = \frac{EV}{AC} \quad \text{（成本绩效指数，} CPI < 1 \text{ 表示超支）}$$

$$SPI = \frac{EV}{PV} \quad \text{（进度绩效指数，} SPI < 1 \text{ 表示滞后）}$$

式中：$PV$ 为计划价值，$EV$ 为挣值，$AC$ 为实际成本。

### 12.2 完工估算

$$EAC = AC + \frac{BAC - EV}{CPI}$$

$$ETC = EAC - AC$$

式中：$BAC$ 为完工预算，$EAC$ 为完工估算，$ETC$ 为完工尚需估算。

**常见错误**：混淆 EV 和 AC；CPI/SPI 仅用累积值忽略趋势分析。

---

## 13. 统计过程控制 (SPC)

### 13.1 控制图

$$UCL = \mu + 3\sigma$$

$$CL = \mu$$

$$LCL = \mu - 3\sigma$$

### 13.2 过程能力指数

$$C_p = \frac{USL - LSL}{6\sigma}$$

$$C_{pk} = \min\left(\frac{USL - \mu}{3\sigma}, \frac{\mu - LSL}{3\sigma}\right)$$

式中：$USL$ 为上规格限，$LSL$ 为下规格限。$C_{pk} \geq 1.33$ 表示过程能力充足。

**常见错误**：未检验正态性就用 $C_{pk}$；控制限计算用了整体标准差而非组内标准差。

---

## 14. 蒙特卡洛模拟

### 14.1 基本步骤公式

$$\hat{\theta} = \frac{1}{N} \sum_{i=1}^{N} f(X_i)$$

$$SE(\hat{\theta}) = \sqrt{\frac{\sum_{i=1}^{N} (f(X_i) - \hat{\theta})^2}{N(N-1)}}$$

式中：$N$ 为模拟次数（通常 $\geq 10000$），$f(X_i)$ 为第 $i$ 次模拟的输出值。

### 14.2 概率分布假设

- 正态分布：$X \sim N(\mu, \sigma^2)$
- 三角分布：$X \sim \text{Tri}(a, b, c)$，$a$ 为最小值，$b$ 为最可能值，$c$ 为最大值
- 均匀分布：$X \sim U(a, b)$

**常见错误**：模拟次数太少（< 1000）；分布假设无依据；未做收敛性检验。

---

## 15. 系统动力学 (SD)

### 15.1 存量-流量方程

$$\frac{dS}{dt} = \sum \text{Inflows} - \sum \text{Outflows}$$

$$S(t) = S(t_0) + \int_{t_0}^{t} \left(\sum \text{Inflows} - \sum \text{Outflows}\right) dt$$

### 15.2 一阶线性系统

$$S(t) = S_0 + (S^* - S_0)(1 - e^{-t/\tau})$$

式中：$S^*$ 为目标值，$\tau$ 为时间常数。

**常见错误**：方程量纲不一致（存量单位 ≠ 流量单位 × 时间）；反馈回路方向标错。

---

## 16. 关键路径法 (CPM)

### 16.1 活动时间估计

$$t_e = \frac{t_o + 4t_m + t_p}{6}$$

$$\sigma^2 = \left(\frac{t_p - t_o}{6}\right)^2$$

式中：$t_o$ 为乐观时间，$t_m$ 为最可能时间，$t_p$ 为悲观时间。

### 16.2 总浮动时间

$$TF_i = LS_i - ES_i = LF_i - EF_i$$

式中：$ES$ 为最早开始，$LS$ 为最晚开始，$EF$ 为最早完成，$LF$ 为最晚完成。$TF = 0$ 的活动在关键路径上。

---

## 17. QFD 质量功能展开

### 17.1 重要度转换

$$W_j = \sum_{i=1}^{m} C_i \cdot R_{ij}$$

式中：$C_i$ 为顾客需求重要度，$R_{ij}$ 为需求-技术关系矩阵中的关系强度（通常用 1-3-5-7-9 标度）。

### 17.2 技术重要度

$$T_j = \frac{W_j}{\sum_{k=1}^{n} W_k} \times 100\%$$

**常见错误**：关系矩阵评分标准不统一；屋顶（技术自相关矩阵）被忽略。

---

## 18. 线性规划

### 18.1 标准型

$$\begin{aligned}
\max \quad & Z = c_1 x_1 + c_2 x_2 + \cdots + c_n x_n \\
\text{s.t.} \quad & a_{11} x_1 + a_{12} x_2 + \cdots + a_{1n} x_n \leq b_1 \\
& a_{21} x_1 + a_{22} x_2 + \cdots + a_{2n} x_n \leq b_2 \\
& \cdots \\
& x_1, x_2, \ldots, x_n \geq 0
\end{aligned}$$

---

## 使用说明

当用户要求为论文中的某个方法生成公式时：
1. 确认方法名称（含别名映射，如 "AHP" = "层次分析法"）
2. 确认使用阶段（发现问题 / 解决问题 / 验证问题），只生成该阶段相关的公式
3. 用正确的 LaTeX 语法生成公式
4. 每个公式后给出变量定义
5. 提示论文中应报告的检验指标（如 AHP 的 CR 值）
6. 检查是否符合"常见错误"中的提醒
