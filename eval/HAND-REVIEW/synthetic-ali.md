# Synthetic golden-question review — ali

For each row: read the exact source excerpt, decide whether the question and expected answer are correct, then fill `reviewed_by`, `decision` (`ok` / `fix`) and `notes` in the CSV. Do not change `judge_supported` in the judge worksheet.

## a03 — Are students allowed to keep pets in their rooms on campus?

- type: abstain; hard: False; must_abstain: True
- declared evidence: (no relevant document declared)
- expect: (abstain)
- source excerpt:
```text
(none — this is an abstain question; check that no document answers it)
```

## h01 — If my overall GPA keeps sitting under two for three terms straight, what happens to my enrolment?

- type: paraphrase; hard: True; must_abstain: False
- declared evidence: academic-rules-handbook-jun-2026.pdf / 5.6
- expect: closed
- source excerpt:
```text
p24: 5. Academic Assessment
5.1 The performance of students is assessed during the semester
through midterm exams, assignments, quizzes, case studies or
any other method considered appropriate by the course
instructor and the University and communicated to the
students at the start of a course.
5.2 The semester work will normally contribute 50% towards the
final grade, while the final examination will contribute the
remaining 50% of the total marks. A letter grade will be
awarded to each student based on his/her overall academic
performance in a course.
5.3 Any deviation from Rule 5.2 above if necessitated by the
nature of course will be made with the approval of Dean of the
Faculty.
Academic Warning/Probation
5.4 Minimum CGPA required to avoid academic warning is 2.00
for all undergraduate programs.
5.5 If at the end of a semester (including summer semester) CGPA
drops below 2.00, warning is issued, and warning count is
incremented by one.
5.6 If CGPA remains below 2.00 for 3 consecutive semesters,
warning count becomes three and the admission of student at
the University is automatically closed.
```

## h03 — Is there a cap on how many courses I can retake over the summer?

- type: paraphrase; hard: True; must_abstain: False
- declared evidence: academic-rules-handbook-jun-2026.pdf / 6.6 | academic-rules-handbook-jun-2026.pdf / 1.19
- expect: 2
- source excerpt:
```text
p28: 6. Rules for Summer Semester
6.1 Summer semester is an 8-week semester and is meant to
facilitate students who are in one of the following four
categories.
A. Academic Warning I/II
B. Graduating
C. Eligible for registering FYP-I in Fall by earning minimum
required credits in the summer
D. Eligible for registering a course/lab in Fall by passing
its pre-requisite in summer
6.2 Any course(s) offered can only be a repeat course. No new
courses are allowed for any of the above four categories
6.3 Students can repeat only such courses, in which they has
registered in a previous semester and was awarded a letter
grade.
6.4 The contact hours per week during the Summer Semester will
be doubled to ensure that the course is completely taught in
summer (with half the duration as compared to a regular
semester).
6.5 Research courses or projects will not be offered.
6.6 A student will be allowed to repeat a maximum of 2 courses
(with associated labs if any).
6.7 80% attendance rule shall apply to summer courses/labs.
```

## h05 — What is the fine for returning a library book late?

- type: batch-b; hard: True; must_abstain: False
- declared evidence: b02-library-borrowing-rules.md / 3.1
- expect: 50
- source excerpt:
```text
p1: # Library Borrowing Rules

1. Membership

1.1 Every enrolled student is a member of the campus library. The university ID card is
the library card; it must be shown for every loan.

2. Loans

2.1 An undergraduate student may borrow up to three books at a time, for fourteen days.
A loan may be renewed twice, online or at the desk, unless another member has reserved
the book.

2.2 Reference books, theses and the current issues of journals are for use in the
library only and are never lent.

3. Fines

3.1 A book returned late is charged a fine of 50 rupees per day per book. A student with
unpaid library fines cannot collect their degree or transcript until the fines are paid.

3.2 A lost or damaged book is replaced by the borrower, or paid for at twice its current
price when a replacement copy cannot be bought.
```

## h07 — Can I keep my smart watch with me during a midterm paper?

- type: batch-b; hard: True; must_abstain: False
- declared evidence: b01-midterm-exam-notice-2026.md / 2.2
- expect: unfair means
- source excerpt:
```text
p1: # Midterm Examination Notice, Fall 2026

1. Schedule

1.1 Midterm examinations for all undergraduate courses are held in week 8 of the
semester, from Monday 19 October to Saturday 24 October 2026. Each paper is 90 minutes.

1.2 The detailed date sheet is published on the student portal at least seven days before
the first paper. Clashes must be reported to the Academic Office within two working days
of publication; clashes reported later are not rescheduled.

2. Conduct

2.1 Students must carry their university ID card to every paper. A student without an ID
card is allowed to sit the paper only after the invigilator records the roll number, and
must show the card at the Academic Office within 24 hours.

2.2 Mobile phones, smart watches and any device that can store or transmit data must be
switched off and placed in bags at the front of the hall. Possession of such a device at
the desk is treated as use of unfair means.

3. Missed papers

3.1 A student who misses a midterm for a documented medical reason may apply for a
retake within three working days of the paper, with the medical certificate attached.
There is no retake for any other reason.
```

## h09 — Who can borrow a laptop under the laptop loan scheme, and what is the charge for returning it late?

- type: batch-b; hard: True; must_abstain: False
- declared evidence: c02-laptop-loan-scheme.pdf / Laptop Loan Scheme
- expect: 200
- source excerpt:
```text
p1: Laptop Loan Scheme
1. Students on need-based financial aid may borrow a laptop for one semester.
Applications are made through the Financial Aid office in the first two weeks.
2. A borrowed laptop is returned in working condition within three days after the
last final examination. A late return is charged 200 rupees per day.
3. Loss or damage is charged at the repair cost or the replacement price.
```

## h08 — How many guests may a graduate bring to the 2026 convocation?

- type: batch-b; hard: True; must_abstain: False
- declared evidence: c01-convocation-notice.pdf / Convocation Notice 2026
- expect: two
- source excerpt:
```text
p1: Convocation Notice 2026
1. The annual convocation for the class of 2026 is held on Saturday 12 December 2026
in the main auditorium. Graduates report at 9:00 for gowns and seating.
2. Each graduate may bring two guests. Guest passes are collected from the Student
Affairs office with the graduate’s ID card until 5 December 2026.
3. A graduate with outstanding dues, including library fines, is not allowed to
receive the degree at the ceremony; the degree is posted after the dues are cleared.
```
