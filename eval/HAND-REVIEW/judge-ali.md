# Faithfulness judge hand-label review — ali

For each row: read the exact context the model saw and decide whether **every** claim in the answer is supported. Write `yes` or `no` in `human_label` in the CSV. Do not edit `judge_supported`.

## g01 — What CGPA does an undergraduate need to stay off academic warning?

- answer: An undergraduate must maintain a CGPA of at least 2.00 to stay off academic warning.
- judge_supported: True (do not edit)
- exact context:
```text
[1] academic-rules-handbook-jun-2026.pdf — 5.4 Academic Warning/Probation (p.24, v=2026-06)
5.4 Academic Warning/Probation
5.4 Minimum CGPA required to avoid academic warning is 2.00 for all undergraduate programs.

[2] academic-rules-handbook-jun-2026.pdf — 5.6 Academic Warning/Probation (p.24, v=2026-06)
5.6 Academic Warning/Probation
5.6 If CGPA remains below 2.00 for 3 consecutive semesters, warning count becomes three and the admission of student at the University is automatically closed.

[3] grading-page.html — Warning/Probation (p.1, v=2026)
Warning/Probation
At the end of every semester (including the first semester and summer semesters), warning is issued provided the CGPA of a student is less than the minimum required for the degree program.
A student with a warning cannot register in a subsequent semester without approval of the relevant Head of Department or any other senior faculty nominated by him.
After each semester (including the summer or the first semester), if the CGPA of a student is less than the required minimum, the Warning Count increases by one.
If Warning Count becomes three, the admission of student at the University is closed.
If the CGPA equals or exceeds the required minimum, the Warning Count becomes zero.
| Programs | Minimum CGPA required to avoid Warning |
 | BBA/BS | 2.0 |
 | MBA/MS | 2.5 |
 | PhD | 3.0 |

[4] grading-page.html — Warning/Probation (p.1, v=2026)
Warning/Probation
the Warning Count becomes zero. | Programs | Minimum CGPA required to avoid Warning | | BBA/BS | 2.0 | | MBA/MS | 2.5 | | PhD | 3.0 |
The admission will be cancelled automatically after completion of maximum duration allowed to earn a degree.

[5] prospectus-2026-academic-rules-and-regulations.pdf — Warning (p.2, v=2026)
Warning
on the degree issued to such high first semester.
a) Must register for all such courses, achievers. b) Application for withdrawal from in which the grade was F or U. course(s) must be countersigned CGPA 3.90 to 4.00 Summa Cum Laude b) Should register for all such by the parent or the guardian of CGPA 3.75 to 3.89 M agna Cum Laude courses, in which the grade was D, the student. CGPA 3.60 to 3.74 Cum Laude D+ or C-.
c) Request for withdrawal must be
c) Should not register for more than submitted to the Head of 11. Academic Warning/Probation five courses. Department (HOD) before the last
a) At the end of every semester d) Students with warning count = 2 day of classes. (including summer semester), MUST not register for a new

[6] academic-rules-handbook-jun-2026.pdf — 5.7 Academic Warning/Probation (p.25, v=2026-06)
5.7 Academic Warning/Probation
5.7 If the CGPA equals or exceeds 2.00 after the 1st or 2nd academic warning, the warning count is reset to zero.
```

## g02 — What happens if my CGPA stays below 2.00 for three semesters in a row?

- answer: Your admission will be closed.
- judge_supported: True (do not edit)
- exact context:
```text
[1] academic-rules-handbook-jun-2026.pdf — 5.6 Academic Warning/Probation (p.24, v=2026-06)
5.6 Academic Warning/Probation
5.6 If CGPA remains below 2.00 for 3 consecutive semesters, warning count becomes three and the admission of student at the University is automatically closed.

[2] academic-rules-handbook-jun-2026.pdf — 5.5 Academic Warning/Probation (p.24, v=2026-06)
5.5 Academic Warning/Probation
5.5 If at the end of a semester (including summer semester) CGPA drops below 2.00, warning is issued, and warning count is incremented by one.

[3] academic-rules-handbook-jun-2026.pdf — 3.28 Closure of Admission (p.17, v=2026-06)
3.28 Closure of Admission
3.28 If the CGPA of an undergraduate student fall below the acceptable threshold of 2.00 for third consecutive semester, then his/her admission is closed.

[4] academic-rules-handbook-jun-2026.pdf — 5.7 Academic Warning/Probation (p.25, v=2026-06)
5.7 Academic Warning/Probation
5.7 If the CGPA equals or exceeds 2.00 after the 1st or 2nd academic warning, the warning count is reset to zero.

[5] grading-page.html — Warning/Probation (p.1, v=2026)
Warning/Probation
At the end of every semester (including the first semester and summer semesters), warning is issued provided the CGPA of a student is less than the minimum required for the degree program.
A student with a warning cannot register in a subsequent semester without approval of the relevant Head of Department or any other senior faculty nominated by him.
After each semester (including the summer or the first semester), if the CGPA of a student is less than the required minimum, the Warning Count increases by one.
If Warning Count becomes three, the admission of student at the University is closed.
If the CGPA equals or exceeds the required minimum, the Warning Count becomes zero.
| Programs | Minimum CGPA required to avoid Warning |
 | BBA/BS | 2.0 |
 | MBA/MS | 2.5 |
 | PhD | 3.0 |

[6] academic-rules-handbook-jun-2026.pdf — 5.4 Academic Warning/Probation (p.24, v=2026-06)
5.4 Academic Warning/Probation
5.4 Minimum CGPA required to avoid academic warning is 2.00 for all undergraduate programs.
```

## g03 — How many courses is the normal course load in a regular semester?

- answer: The normal course load in a regular semester is 5 courses.
- judge_supported: True (do not edit)
- exact context:
```text
[1] academic-rules-handbook-jun-2026.pdf — 1.17 Scheduling of Classes (p.9, v=2026-06)
1.17 Scheduling of Classes
1.17 Normal semester course load for undergraduate students, who are not on academic warning/probation, is as per the University study plan.

[2] academic-rules-handbook-jun-2026.pdf — 4.3 Registration (p.19, v=2026-06)
4.3 Registration
4.3 The normal course load is 5 courses. A final year student may register in one additional course (inclusive of Final Year Project-FYP).

[3] prospectus-2026-academic-rules-and-regulations.pdf — 4 Semester Course Load (p.1, v=2026)
4 Semester Course Load
Each course is assigned credit hours. For theory courses 1 credit hour means 1 hour of lecturing per week, while for lab courses 1 credit hour means 3 hours of labwork per week. For example, a 3+1 credit hour course carries 3 hours of lectures and 3 hours of labwork per week. Normal course load for undergraduate students is as prescribed in the study plan.

[4] academic-rules-handbook-jun-2026.pdf — 1.6 Academic Year (p.7, v=2026-06)
1.6 Academic Year
1.6 A regular semester is spread over 16 weeks of teaching, one makeup week and 2 weeks of final examinations.

[5] academic-rules-handbook-jun-2026.pdf — 6.4 B. Graduating (p.28, v=2026-06)
6.4 B. Graduating
6.4 The contact hours per week during the Summer Semester will be doubled to ensure that the course is completely taught in summer (with half the duration as compared to a regular semester).

[6] student-handbook-jun-2026.pdf — Code Of Conduct (p.11, v=2026-06)
Code Of Conduct
code of conduct by the student. 18. It is generally recommended that students only take the recommended course load per semester (5 courses for BS and 3 courses for MS).
This keeps the workload manageable and allows student to perform reasonably well in a semester.
19. Late submissions in assessment are not accepted and strongly discouraged.
```

## g04 — How many courses can I repeat in the summer semester?

- answer: You can repeat up to two courses in the summer semester.
- judge_supported: True (do not edit)
- exact context:
```text
[1] prospectus-2026-academic-rules-and-regulations.pdf — 19 Rules for Summer Semester (p.3, v=2026)
19 Rules for Summer Semester
doubled to ensure that the course is completely taught in summer (with half the duration as compared to a regular semester). d) Research courses or projects will not be offered.
e) A student will be allowed to repeat a maximum of 2 courses (with associated labs if any).
f) 80% attendance rule shall applytosummer courses/labs.
g) A student can withdraw from a summer course on or before the last day of classes.
h) Summer courses cannot be dropped; hence, fee is neither refunded nor carried forward to next semester(s).
i) Financialassistance , scholarship or fee concession is not available in summer semester.
j) A minimum of TEN (10) students should register in a summer course. Otherwise, the course shall be dropped.
k) WarningCountis incremented/decremented in summer semester.

[2] prospectus-2026-academic-rules-and-regulations.pdf — 19 Rules for Summer Semester (p.3, v=2026)
19 Rules for Summer Semester
Summer semester is an 8-week semester and is meant to facilitate students who are in one of the following four categories.
i) Academic Warning I/II
ii) Graduating
iii) Eligible for registering FYP-I in Fall by earning minimum required credits in the summer
iv) Eligible for registering a course/lab in Fall by passing its pre-requisite in summer
a) Any course(s) offered can only be a repeat course. No new courses are allowed for
any of the above four categories
b) Students can repeat only such courses, in which they has registered in a previous semester and was awarded a letter grade.
c) The contact hours per week during the Summer Semester will be doubled to ensure that the course is completely taught in summer (with half the duration as compared to a regular semester).
d) Research courses or projects will not be offered.

[3] academic-rules-handbook-jun-2026.pdf — 1.19 Scheduling of Classes (p.9, v=2026-06)
1.19 Scheduling of Classes
1.19 A student can register for a maximum of two courses in summer semester in accordance with the rules for summer semester. For more details, please see rule no 6: Rules for Summer Semester.

[4] prospectus-2026-academic-rules-and-regulations.pdf — 19 Rules for Summer Semester (p.3, v=2026)
19 Rules for Summer Semester
not available in summer semester. j) A minimum of TEN (10) students should register in a summer course. Otherwise, the course shall be dropped. k) WarningCountis incremented/decremented in summer semester.
l) A student can study summer semester in another campus, provided that the parent campus is not offering that course. Student must obtain, in writing, prior permission from Director of the parent campus.

[5] academic-rules-handbook-jun-2026.pdf — 6.4 B. Graduating (p.28, v=2026-06)
6.4 B. Graduating
6.4 The contact hours per week during the Summer Semester will be doubled to ensure that the course is completely taught in summer (with half the duration as compared to a regular semester).

[6] academic-rules-handbook-jun-2026.pdf — 6.11 B. Graduating (p.29, v=2026-06)
6.11 B. Graduating
6.11 A minimum of TEN (10) students should register in a summer course. Otherwise, the course shall be dropped.
```

## g05 — If I apply for rechecking of my final exam, do I get the rechecking fee back?

- answer: Yes, the rechecking fee will be refunded if there is an increase in marks.
- judge_supported: True (do not edit)
- exact context:
```text
[1] academic-rules-handbook-jun-2026.pdf — 5.25 Rechecking of Final Exams (p.27, v=2026-06)
5.25 Rechecking of Final Exams
5.25 Rechecking fee will be refunded if there is an increase in marks.

[2] academic-rules-handbook-jun-2026.pdf — 5.20 Rechecking of Final Exams (p.26, v=2026-06)
5.20 Rechecking of Final Exams
5.20 Application to recheck a final exam must be submitted on prescribed form together with rechecking fee.

[3] academic-rules-handbook-jun-2026.pdf — 5.24 Rechecking of Final Exams (p.27, v=2026-06)
5.24 Rechecking of Final Exams
5.24 A student who has not viewed his final exam paper in the scheduled paper viewing session may also request rechecking of the final examination by paying the prescribed fee.

[4] academic-rules-handbook-jun-2026.pdf — 5.23 Rechecking of Final Exams (p.27, v=2026-06)
5.23 Rechecking of Final Exams
5.23 Examination Office will inform the student about the outcome of the rechecking application.

[5] academic-rules-handbook-jun-2026.pdf — 5.22 Rechecking of Final Exams (p.27, v=2026-06)
5.22 Rechecking of Final Exams
5.22 Committee should adhere to the following guidelines to handle rechecking cases:
a) Committee should recount marks awarded by the concerned instructor.
b) Unmarked question or part should be sent to the instructor for checking/marking.
c) Committee should not discuss the outcome of the rechecking with the students.
d) Committee recommendation should be submitted to the Director’s office using the Change of Grade Form for final approval.

[6] academic-rules-handbook-jun-2026.pdf — 5.21 Rechecking of Final Exams (p.27, v=2026-06)
5.21 Rechecking of Final Exams
5.21 Student application should reach the Examination Office within seven days of the announcement of the result.
```

## g06 — Am I allowed to use ChatGPT or other generative AI tools in lab courses like Programming Fundamentals?

- answer: No, you are not allowed to use ChatGPT or other generative AI tools in lab courses such as Programming Fundamentals unless the lab instructor explicitly permits it.
- judge_supported: True (do not edit)
- exact context:
```text
[1] academic-rules-handbook-jun-2026.pdf — 6.2 Use in Lab Courses (p.50, v=2026-06)
6.2 Use in Lab Courses
1) In general, the use of generative AI tools like ChatGPT in labs is prohibited unless explicitly allowed by the lab instructor, particularly in courses such as Programming Fundamentals

[2] student-handbook-jun-2026.pdf — 6.2 Use in Lab Courses (p.57, v=2026-06)
6.2 Use in Lab Courses
1) In general, the use of generative AI tools like ChatGPT in labs is prohibited unless explicitly allowed by the lab instructor, particularly in courses such as Programming

[3] academic-rules-handbook-jun-2026.pdf — 6.1 Use in Non-Lab Courses (p.49, v=2026-06)
6.1 Use in Non-Lab Courses
1) Students are allowed, and sometimes encouraged, to use generative AI tools like ChatGPT for completing course assignments. 2) All the course assignments must include associated quizzes or demonstrations. 3) A small percentage (typically 10-15%) of the total marks will be allotted to the assignment submissions. The majority of the marks will be based on the assignment quizzes or demonstrations. This grading distribution should be clearly stated in the course outline. These quizzes or demonstrations should take place in the week following the submission deadline. 4) Faculty members are encouraged to integrate questions related to these assignments into both sessional and final exams.
5) Students should be encouraged to submit the prompts they used in generative AI tools to understand the assignments. Instructors can use these prompts to identify students' weaknesses by analyzing the approach they took to comprehend the material.

[4] student-handbook-jun-2026.pdf — 6.1 Use in Non-Lab Courses (p.56, v=2026-06)
6.1 Use in Non-Lab Courses
1) Students are allowed, and sometimes encouraged, to use generative AI tools like ChatGPT for completing course assignments. 2) All the course assignments must include associated quizzes or demonstrations. 3) A small percentage (typically 10-15%) of the total marks will be allotted to the assignment submissions. The majority of the marks will be based on the assignment quizzes or demonstrations. This grading distribution should be clearly stated in the course outline. These quizzes or demonstrations should take place in the week following the submission deadline. 4) Faculty members are encouraged to integrate questions related to these assignments into both sessional and final
exams. 5) Students should be encouraged to submit the prompts they used in generative AI tools to understand the assignments. Instructors can use these prompts to identify students' weaknesses by analyzing the approach they took to comprehend the material.

[5] academic-rules-handbook-jun-2026.pdf — 6.3 Use in Research (p.51, v=2026-06)
6.3 Use in Research
1) Generative AI tools like ChatGPT are to be used as assistive tools for research purposes only. They should enhance productivity, explore ideas, and provide insights while preserving the integrity of the research process. 2) Researchers and students intending to use generative AI in their research must undergo appropriate training to understand its capabilities and limitations. They should also be familiar with the University’s policies on academic integrity and the responsible use of AI tools. 3) The use of generative AI in research projects must be reviewed and approved by relevant faculty members, advisors, or supervisors to ensure compliance with University policy and alignment with research objectives. 4) Generative AI should not be used for the automated submission of research work, assignments, or any other academic assessments. All submissions must be the original work of the researchers.

[6] student-handbook-jun-2026.pdf — 6.3 Use in Research (p.57, v=2026-06)
6.3 Use in Research
1) Generative AI tools like ChatGPT are to be used as assistive tools for research purposes only. They should enhance productivity, explore ideas, and provide insights while preserving the integrity of the research process.
2) Researchers and students intending to use generative AI in their research must undergo appropriate training to understand its capabilities and limitations. They should also be familiar with the University’s policies on academic integrity and the responsible use of AI tools. 3) The use of generative AI in research projects must be reviewed and approved by relevant faculty members, advisors, or supervisors to ensure compliance with University policy and alignment with research objectives. 4) Generative AI should not be used for the automated submission of research work, assignments, or any other academic assessments. All submissions must be the original work of the researchers.
```
