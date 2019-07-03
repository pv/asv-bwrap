prepare_asv() {
    if [ -d repo ]; then
        run git -C repo fetch --tags
        run git -C repo reset --hard origin/master
        run git -C repo submodule update --init
    else
        run git clone --recurse-submodules "$REPO_URL" repo
    fi

    run cd "$HOME/repo"
    if [ "$REPO_SUBDIR" != "" ]; then
        run cd "$REPO_SUBDIR"
    fi
    rm -rf results .asv/results
    mkdir -p .asv
    ln -s /home/results results
    ln -s /home/results .asv/results
    if [ ! -f $HOME/.asv-machine.json ]; then run asv machine --yes; echo; fi
}

copy_html() {
    if [ -d .asv/html ]; then run rsync -a --delete .asv/html/ /home/html/; fi
    if [ -d html ]; then run rsync -a --delete html/ /home/html/; fi
}
