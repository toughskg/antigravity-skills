def GetPrimes(num):
  l = []
  # This function gets all prime numbers up to num
  for i in range(0, num):
    flag = False
    if i > 1:
      # Slow loop, checking everything up to i
      for j in range(2, i):
        if (i % j) == 0:
          flag = True
          break
      if flag:
        pass
      else:
        l.append(i)
  return l

result = GetPrimes(100)
print(result)
