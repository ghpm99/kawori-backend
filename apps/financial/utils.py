

def calculate_installments(value, installments):

    def round(num):
        return float('%.2f' % (num))

    values = []

    if installments == 1:
        values.append(value)
        return values

    value_total = value
    index = installments
    value_installments = round(value / installments)

    for i in range(index):
        if i == index - 1:
            values.append(round(value_total))
        else:
            values.append(value_installments)
            value_total = value_total - value_installments

    return values
