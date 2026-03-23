class TotalVotesUseCase:
    def execute(self, answer_model):
        return {"total_votes": answer_model.objects.count()}, 200
