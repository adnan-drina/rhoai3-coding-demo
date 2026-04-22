"""Rock, Paper, Scissors — starter code for AI code improvement demo.

Ask the AI code assistant to make this code more "enterprise-grade":
- Add input validation
- Add error handling
- Add type hints
- Add logging
- Make it testable
"""

import random

def play():
    choices = ["rock", "paper", "scissors"]
    user = input("Enter rock, paper, or scissors: ")
    computer = random.choice(choices)
    print(f"Computer chose: {computer}")

    if user == computer:
        print("It's a tie!")
    elif (user == "rock" and computer == "scissors") or \
         (user == "scissors" and computer == "paper") or \
         (user == "paper" and computer == "rock"):
        print("You win!")
    else:
        print("You lose!")

if __name__ == "__main__":
    play()
