import time
import threading

def is_prime(n):
    """Check if a number is a prime number."""
    if n <= 1:
        return False
    if n <= 3:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True

def compute_primes(start, end):
    """Compute and return prime numbers in a given range."""
    primes = []
    for num in range(start, end):
        if is_prime(num):
            primes.append(num)
    return primes

def resource_heavy_task(start, end):
    """Perform a resource-heavy task by computing prime numbers."""
    while True:
        primes = compute_primes(start, end)
        print(f"Found {len(primes)} primes from {start} to {end}.")

def main():
    num_threads = 4
    ranges = [(i * 250000, (i + 1) * 250000) for i in range(num_threads)]
    
    threads = []
    
    # Create and start threads
    for start, end in ranges:
        thread = threading.Thread(target=resource_heavy_task, args=(start, end))
        threads.append(thread)
        thread.start()
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(60)  # Sleep for a minute and let threads run indefinitely
    except KeyboardInterrupt:
        print("Interrupted by user, terminating.")

if __name__ == "__main__":
    main()
