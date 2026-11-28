# Faithfulness judge hand-label review — taimoor

For each row: read the exact context the model saw and decide whether **every** claim in the answer is supported. Write `yes` or `no` in `human_label` in the CSV. Do not edit `judge_supported`.

## g07 — How much is the admission fee, and is it refundable?

- answer: The admission fee is Rs 30,000 and it is non‑refundable.
- judge_supported: True (do not edit)
- exact context:
```text
[1] fee-structure-page.html — Admission Fee (p.1, v=2026-27)
Admission Fee
Admission Fee of Rs 30,000 is payable once at the time of admission. If a graduate of this University is admitted to a higher degree program, then admission fee is not payable again.

[2] fee-structure-page.html — Fee Refund Policy (p.1, v=2026-27)
Fee Refund Policy
1. Admission Fee is non-refundable.
2. Security deposit is refundable at the time of completion of degree or closing of admission.
3. Tuition Fee is refunded in accordance with the guidelines of Higher Education Commission (HEC).
| Timeline | Percentage of Fee |
 | Upto 10th day of commencement of classes | 100% Fee Refund |
 | Upto 15th day of commencement of classes | 80% Fee Refund |
 | Upto 20th day of commencement of classes | 60% Fee Refund |
 | Upto 30th day of commencement of classes | 50% Fee Refund |
 | 31st day onwards of commencement of classes | No Refund |
Note: Days shall be counted including working days and holidays.

[3] fee-structure-page.html — Security Deposit (p.1, v=2026-27)
Security Deposit
A refundable security deposit of Rs 20,000 is also payable at the time of admission.

[4] fee-structure-page.html — Fee Refund Policy (p.1, v=2026-27)
Fee Refund Policy
commencement of classes | 50% Fee Refund | | 31st day onwards of commencement of classes | No Refund | Note: Days shall be counted including working days and holidays.
After declaration of FSc/A Level/Equivalent result, admission of a student stands cancelled if he/she fails to meet the required eligibility requirement for admission. The fee refund is calculated from the date of his/her result announcement.

[5] student-handbook-jun-2026.pdf — Fee Structure and Mode of Payment (p.18, v=2026-06)
Fee Structure and Mode of Payment
The fee is charged on Semester basis, and it becomes due two weeks earlier than the start of a semester at the time of course registration. Fees are paid in the bank through bank challan available in Accounts Office/Flex. All fees are non-Refundable All fees are non-refundable (except security deposit) and the University reserves the right to review the fee structure from time to time. Any revision of fees would be uniformly applicable to all students at the University.

[6] fee-structure-page.html — Miscellaneous Fees (p.1, v=2026-27)
Miscellaneous Fees
| Additional Transcript Fee | Rs. 300 |
 | Campus Transfer Fee | Rs. 5,000 |
 | Temporary Campus Transfer Fee | Rs. 2,000 |
 | Degree Correction Fee | Rs. 2,000 |
 | Semester Freeze Fee (within two weeks of start of classes) | Rs. 2,000 |
 | Late Registration Fee/Freeze Fee/Course Withdrawal (After second week of start of classes) | 5,000 |
 | Retake Sessional Exam Fee (Per Course) | Rs. 2,000 |
 | Retake Final Exam Fee (Per Course/Lab) | Rs. 2,000 |
 | Paper Rechecking Fee (Per Course/Lab) | Rs. 500 |
 | Issuance of Certificate/Letter Fee | Rs. 300 |
 | Applicant Admission Fee | Rs. 3,000 |
 | These fees are non-refundable. |
```

## g08 — How many grade points is a B+ worth?

- answer: 3.33
- judge_supported: True (do not edit)
- exact context:
```text
[1] academic-rules-handbook-jun-2026.pdf — 2.3 Grade Points (p.12, v=2026-06)
2.3 Grade Points
2.3 The points for each letter grade are given as follows:
| Grade | Points | Grade | Points |
 | A+ | 4.00 | C+ | 2.33 |
 | A | 4.00 | C | 2.00 |
 | A- | 3.67 | C- | 1.67 |
 | B+ | 3.33 | D+ | 1.33 |
 | B | 3.00 | D | 1.00 |
 | B- | 2.67 | F | 0.00 |

[2] prospectus-2026-academic-rules-and-regulations.pdf — B+ 3.33 (p.1, v=2026)
B+ 3.33
The following letter grades are common to all degree programs:

[3] grading-page.html — Letter Code Interpretation (p.1, v=2026)
Letter Code Interpretation
Letter grades for BBA & BS programs
| Grade | Points | Interpretation |
 | A+ | 4.00 | Excellent |
 | A | 4.00 | Excellent |
 | A- | 3.67 | Very Good |
 | B+ | 3.33 | Very Good |
 | B | 3.00 | Good |
 | B- | 2.67 | Average |
 | C+ | 2.33 | Below Average |
 | C | 2.00 | Adequate |
 | C- | 1.67 | Pass |
 | D+ | 1.33 | Pass |
 | D | 1.00 | Pass |
Letter grades for MBA & MS programs

[4] prospectus-2026-academic-rules-and-regulations.pdf — The Grade Point Average (GPA) (p.1, v=2026)
The Grade Point Average (GPA)
provides a continuous scale (0.00 to 4.00) for grades earned. Two types of averages are computed using the grades obtained by the student, the Semester Grade

[5] academic-rules-handbook-jun-2026.pdf — 2.1 Grade Point Average (p.11, v=2026-06)
2.1 Grade Point Average
2.1 The Grade Point Average (GPA) provides a continuous scale for grades earned. Two types of averages are computed for the grades obtained by a student, the Semester Grade Point

[6] prospectus-2026-academic-rules-and-regulations.pdf — Eachlettergradehas (p.1, v=2026)
Eachlettergradehas
corresponding numeric points. Thepointsa re usedfor calculating the Grade Point Average (GPA). etter grades for BS & BBA programs: Gr ade Po ints Grade Points
```

## g09 — What is the maximum time allowed to complete a bachelor's degree?

- answer: The maximum time allowed to complete a bachelor’s degree is six years, extendable for one additional year with approval of the Statutory Bodies.
- judge_supported: True (do not edit)
- exact context:
```text
[1] academic-rules-handbook-jun-2026.pdf — 1.23 Bachelor’s Degree Requirements (p.10, v=2026-06)
1.23 Bachelor’s Degree Requirements
1.23 The minimum duration of a Bachelor’s degree is four academic years (8 regular semesters) and a maximum time limit of 6 years, further extendable for one year with the approval of Statutory Bodies.

[2] academic-rules-handbook-jun-2026.pdf — 1.24 Bachelor’s Degree Requirements (p.10, v=2026-06)
1.24 Bachelor’s Degree Requirements
1.24 When a student is readmitted with credit exemptions from a previous admission, the maximum duration allowed to complete the degree will be counted from the date of first admission.

[3] prospectus-2026-academic-rules-and-regulations.pdf — 3 Disciplinary Action 34. Maximum Time Allowed to (p.5, v=2026)
3 Disciplinary Action 34. Maximum Time Allowed to
To maintain an academic and Complete Degree Requirements comfortable environment at the As per HEC guidelines, the campus, students must abide by maximum period allowed to fulfil the rules and regulations of the degree requirements is given University and to follow a code of below: conduct.
Students are expected BS/BBA programs Six (6)* years toobservedisciplinary MBA programs Three (3) years standards of the University in all MS programs Four (4) years their dealings.
Failure to do so PhD programs Eight (8) years shall require appearance before a disciplinary committee.
The *Further extendable for one year with committee shall recommend the approval of Statutory Bodies suitable action against the Extensions will only be granted for student.

[4] prospectus-2026-academic-rules-and-regulations.pdf — 3 Disciplinary Action 34. Maximum Time Allowed to (p.5, v=2026)
3 Disciplinary Action 34. Maximum Time Allowed to
before a disciplinary committee. The *Further extendable for one year with committee shall recommend the approval of Statutory Bodies suitable action against the Extensions will only be granted for student.
The action may amount genuine and unavoidable to imposition of fine, suspension, circumstances that have prevented expulsion, or disqualification of student from timely completing their a student from any academic degree such as Iddat, Maternity, honour such as award of a Death in the immediate family medal, scholarship, etc.
The member and medical condition. following will call for disciplinary action.
When a student is readmitted with
a) Disregard or disobedience of credit exemptions from a previous rules of the University admission, the maximum duration
b) Willfulde fi anceof allowed to complete the degree will Unive rs i t y 'sauthority be counted from the date of first whetheraloneorin admission. association with others

[5] academic-rules-handbook-jun-2026.pdf — 3.29 Closure of Admission (p.17, v=2026-06)
3.29 Closure of Admission
3.29 A student’s admission will be cancelled automatically after completion of maximum duration allowed to earn a degree unless extension is approved by competent authority.

[6] faculty-entrepreneurship-and-technical-start-ups-policy.pdf — Terms (p.7, v=2022-05)
Terms
taking members from both sides, or from other university/IP office) to solve the issue. 7. The Maximum duration of this agreement will be two years for the date of signing.
8. Failure to abide the rules and regulation will lead to the immediate termination of the
agreement.
```

## g10 — What SGPA do I need to be included in the Rector's List of Honors?

- answer: SGPA of 4.00
- judge_supported: True (do not edit)
- exact context:
```text
[1] academic-rules-handbook-jun-2026.pdf — 7.3 Rector’s List of Honors (p.30, v=2026-06)
7.3 Rector’s List of Honors
7.3 Students earning an SGPA of 4.00 with at least 30 credit hours shall be included in a prestigious list called Rector’s List of
Honors.

[2] academic-rules-handbook-jun-2026.pdf — 7.6 Dean's List of Honors (p.31, v=2026-06)
7.6 Dean's List of Honors
7.6 Students with an SGPA of 3.50 to 3.99 would be included in The Dean's List of Honors which shall be maintained in each campus at a prominent place to give recognition to their distinguished performance.

[3] academic-rules-handbook-jun-2026.pdf — 7.4 Rector’s List of Honors (p.31, v=2026-06)
7.4 Rector’s List of Honors
7.4 The Rector's list will be issued and displayed after each semester and a recognition certificate will be issued. Student’s name is also placed on the University’s website.

[4] academic-rules-handbook-jun-2026.pdf — 7.5 Rector’s List of Honors (p.31, v=2026-06)
7.5 Rector’s List of Honors
7.5 Only those students are included in this list who have completed the semester with regular course load prescribed in the study plan.

[5] academic-rules-handbook-jun-2026.pdf — 7.10 Dean's List of Honors (p.31, v=2026-06)
7.10 Dean's List of Honors
7.10 Eligibility for the medals and certificate is as follows:
a) Student must have passed the standard courses (core and elective), labs and final year projects of the degree offered by the department in a semester to a batch with a specified number of total credit hours
b) Student must not have failed, repeated or withdrawn from a course in that semester. Only those students are included in this list who have completed the semester with regular course load prescribed in the study plan
c) Position is determined by the GPA earned in that semester.
d) Student must have earned GPA of 3.00 or higher in that semester.

[6] prospectus-2026-academic-rules-and-regulations.pdf — 3.99 Academic Rules & Regulations FA S T- NUCES (p.2, v=2026)
3.99 Academic Rules & Regulations FA S T- NUCES
student is placed on the Rector's except those on academic Students on academic warning List, if his/her SGPA is 4.00 in a warning. The recommended cannot register for FYP-I. semester.
The student receives a registration procedure is as Registration in FYP-II is allowed Certificate and his/her name is follows: only after successful completion also placed on the University's a) Clear all previous fees and of FYP-I. website.
Only those students are dues before registration. included in this list who have b) First semester students 15.
Adding or Dropping a Course completed the semester with should register through the The request should be made regular course load prescribed in Academic Office.
All other within the first two weeks of a the study plan. students should register semester.
Approval of the Head of online.
Department is essential.
Students 10.
```

## g12 — How long must a faculty member have worked full-time at NUCES to be eligible to set up a technical start-up?

- answer: A faculty member must have worked full‑time at NUCES for more than 1 year.
- judge_supported: True (do not edit)
- exact context:
```text
[1] faculty-entrepreneurship-and-technical-start-ups-policy.pdf — 1 Purpose (p.1, v=2022-05)
1 Purpose
REB
4.2. 4.3.
4.4.
sls
ty
BwWN ee
Following are the guideline for “Faculty Entrepreneurship/Technical Start-up”, for the fulltime faculty members of National University of Computer and Emerging Sciences (NUCES), Pakistan. The guidelines are limited to technical and innovative start-ups that aim to commercialize research conducted at NUCES Campuses. The Faculty Entrepreneurship, for the purpose of this policy, is defined as the involvement of NUCES faculty in:
founding or management of a technical start-up,
holding significant share/equity of the company,
as member of the governing board of the start-up,
as recipient of a share of revenue of the start-up.

[2] faculty-entrepreneurship-and-technical-start-ups-policy.pdf — Objectives (p.1, v=2022-05)
Objectives
their university courses. To support the university in meeting commercialization requirements set by HEC. To attract and retain high quality faculty members by providing an opportunity for commercialization of research.
Eligibility criteria for a technical start-up Faculty member must be a “full-time” faculty member at any of the campuses of the university. Faculty member must have been a full-time faculty member for more than 1 year. The start-up must be based on some research work (as part of internal or externally funded project, student final year project, or student research thesis or any other research/innovation work carried out at NUCES). A licensing agreement, grantin g the startup the right to use the university IP at no initial cost for 2 years, shall be signed between the university and the start-up.

[3] faculty-entrepreneurship-and-technical-start-ups-policy.pdf — Pele (p.2, v=2022-05)
Pele
Policy available at university website). List of NUCES faculty members and staff involved in the start-up Applications must be submitted through the campus Director office. Procedure for evaluating the application
The Campus Director shall provide comments, recommend the application and forward the application to ORIC.
ORIC shall evaluate and recommend the application using the criteria provided in Section 5).
For final approval, the cases shall be presented to the RECTOR NUCES for approval. The decision by the RECTOR is final in this regard.
Mandatory periodic (six. monthly) deliverables of the start-up Approximate business/funds being generated by the start-up.
Number of employments created by the start-up.
Summary of industry partnerships generated by the start-up.
Patents held by university being commercialized by the start-up...
Any new patents registered by the start-up
Marketing material / evidence of commercialization activities by the start-up
Other terms and conditions

[4] faculty-entrepreneurship-and-technical-start-ups-policy.pdf — Scope (p.1, v=2022-05)
Scope
The policy covers the grant of permission to full-time NUCES faculty members to participate in “Faculty Entrepreneurship”, as defined in (1.2) to encourage faculty members initiating /actively participating in setting up commercialization opportunities.
The policy defines the objectives, eligibility criteria for the applicants seeking to creating new start-ups, the evaluation criteria for approval of applications, the procedure for submission of applications, their evaluation, and requirements of periodic reporting to the university on the progress of the start-up.

[5] faculty-entrepreneurship-and-technical-start-ups-policy.pdf — Pele (p.2, v=2022-05)
Pele
72.
Tid
Evaluation criteria for a technical start-up Faculty member must have published one journal paper (at least online with a DOI number), with the impact factor journals appearing in Journal Citation Reports by Web of Science Group (JCR) within two years prior to the date of application with NUCES affiliation.
Faculty member must have completed or currently be involved as a Principal Investigator or Co-Principal Investigator of an externally funded research project of significant funding amount within the last five year. The start-up should align with the ongoing research at the university and the university degree programs.
The start-up should be related to emerging technologies and should be aiming to commercialise the research of faculty members or research projects.
a

[6] faculty-entrepreneurship-and-technical-start-ups-policy.pdf — Pele (p.3, v=2022-05)
Pele
No workload exemption shall be provided to the applicant for creating /managing the startup. Applicants are expected to complete all their obligations and responsibilities assigned to them by the university.
While the faculty members may be involved in the start-ups, they cannot hold sole management role in the company. A full-time Chief Executive/ Managing Director/ Chief Operations Officers or equivalent position should be filled for managing day-to-day operations of the company.
The start-up may not engage university students in a manner that creates conflict of interest (for example, by utilizing work completed by students as part of their courses).
The university has the right to advertise the start-up and its product descriptions and marketing materials, and other disclosed information (such as number of jobs created) for promotional activities, and for meeting documenting requirements of HEC, ranking /accreditation bodies, etc.
```

## v01 — What is the deadline to withdraw from a course?

- answer: The deadline to withdraw from a course is the last day of the makeup week of every semester.
- judge_supported: True (do not edit)
- exact context:
```text
[1] academic-rules-handbook-jun-2026.pdf — 4.25 Withdrawal from a Course (p.23, v=2026-06)
4.25 Withdrawal from a Course
4.25 The deadline to withdraw from a course is the last day of the makeup week of every semester.

[2] academic-rules-handbook-jun-2026.pdf — 4.24 Withdrawal from a Course (p.22, v=2026-06)
4.24 Withdrawal from a Course
4.24 Students are not allowed to withdraw from any course in the first semester unless necessitated by unavoidable circumstances. Such a request must be approved by the Director of the campus.

[3] academic-rules-handbook-jun-2026.pdf — 4.23 Withdrawal from a Course (p.22, v=2026-06)
4.23 Withdrawal from a Course
4.23 Application for withdrawal from a course must be countersigned by the parent or the guardian of the student. Request for withdrawal must be approved by the HoD.

[4] academic-rules-handbook-jun-2026.pdf — 6.8 B. Graduating (p.29, v=2026-06)
6.8 B. Graduating
6.8 A student can withdraw from a summer course on or before the last day of classes.

[5] academic-rules-handbook-jun-2026.pdf — 4.26 Withdrawal from a Course (p.23, v=2026-06)
4.26 Withdrawal from a Course
4.26 Students on any form of financial support are not allowed to withdraw from any course.

[6] prospectus-2026-academic-rules-and-regulations.pdf — Warning (p.2, v=2026)
Warning
(HOD) before the last a) At the end of every semester d) Students with warning count = 2 day of classes. (including summer semester), MUST not register for a new
d) Request to withdraw from a warning is issued if the CGPA of a course. course requires approval of the student is less than the minimum e) Parents/guardians are called to HOD. re q u i re dforg ra duation . the campus for a consultative
e) For courses having an associated Minimum CGPA required to avoid meeting with the HOD. lab, withdrawal is always from academic warning: f) Must obtain written approval both theory and lab portions of BS/BBA programs 2.00 from their Head of Department the course. MS/MBA programs 2.50 for each course that they register,
f) Fee is not refunded for withdrawn PhD programs 3.00 add, drop or withdraw. course.
g) Studentsstudyingunder
```
