import typer
app=typer.Typer()
@app.command()
def train(): print("TODO: train")
@app.command()
def scan(limit:int=100,dry_run:bool=False): print(limit,dry_run)
@app.command()
def report(): print("TODO")
if __name__=="__main__": app()
